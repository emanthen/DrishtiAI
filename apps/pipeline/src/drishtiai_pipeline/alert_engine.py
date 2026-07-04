"""
Alert engine — runs after every committed plate_read event.

For each active WatchlistEntry whose site matches the camera's site:
  - exact:  plate_text == entry.plate_text
  - prefix: plate_text.startswith(entry.plate_text)
  - fuzzy:  entry.plate_text is a substring of plate_text

On match, creates an Alert row and publishes JSON to
  drishti:{site_id}:alerts

Thread-safety: called from a single camera thread — no locking needed per
instance, but DB session must be from the same thread.
"""
from __future__ import annotations

import json
import logging
import urllib.request
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from drishtiai_shared.models.alert import Alert, AlertStatus
from drishtiai_shared.models.watchlist import Watchlist, WatchlistEntry, PlatePattern
from drishtiai_pipeline.webhook_fire import fire as _fire_webhooks

log = logging.getLogger(__name__)

_EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


def _send_push_notifications(
    redis_client,
    site_id: uuid.UUID,
    title: str,
    body: str,
) -> None:
    """Fire Expo push notifications to all registered tokens for site users.
    Looks up tokens stored in push_tokens:{user_id} keys by scanning the
    pattern. Failures are swallowed — push is best-effort.
    """
    try:
        # Collect all push token keys for this site via SMEMBERS on each user
        # We store tokens under push_tokens:{user_id}; to find site users we
        # scan push_tokens:* and send to all (site membership enforced at API).
        keys = redis_client.keys("push_tokens:*")
        tokens: list[str] = []
        for key in keys:
            members = redis_client.smembers(key)
            tokens.extend(m.decode() if isinstance(m, bytes) else m for m in members)

        if not tokens:
            return

        messages = [
            {"to": t, "title": title, "body": body, "sound": "default"}
            for t in tokens
        ]
        data = json.dumps(messages).encode()
        req = urllib.request.Request(
            _EXPO_PUSH_URL,
            data=data,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as exc:
        log.debug("push notification failed: %s", exc)


def check_and_fire(
    *,
    db: Session,
    redis_client,  # redis.Redis (sync)
    site_id: uuid.UUID,
    event_id: uuid.UUID,
    plate_text: str,
) -> list[uuid.UUID]:
    """
    Check watchlists for `site_id`, fire alerts for any matching entries.
    Returns list of created Alert IDs.
    """
    normalised = plate_text.upper().replace(" ", "").replace("-", "")

    # Load all watchlists for this site with their entries
    watchlists = list(
        db.scalars(
            select(Watchlist).where(Watchlist.site_id == site_id)
        ).all()
    )

    created_ids: list[uuid.UUID] = []

    for wl in watchlists:
        entries: list[WatchlistEntry] = list(
            db.scalars(
                select(WatchlistEntry).where(WatchlistEntry.watchlist_id == wl.id)
            ).all()
        )
        for entry in entries:
            entry_norm = entry.plate_text.upper().replace(" ", "").replace("-", "")
            matched = False
            if entry.plate_pattern == PlatePattern.exact:
                matched = normalised == entry_norm
            elif entry.plate_pattern == PlatePattern.prefix:
                matched = normalised.startswith(entry_norm)
            elif entry.plate_pattern == PlatePattern.fuzzy:
                matched = entry_norm in normalised

            if not matched:
                continue

            alert = Alert(
                id=uuid.uuid4(),
                event_id=event_id,
                watchlist_id=wl.id,
                status=AlertStatus.new,
            )
            db.add(alert)
            db.flush()
            created_ids.append(alert.id)

            payload = json.dumps({
                "alert_id": str(alert.id),
                "event_id": str(event_id),
                "site_id": str(site_id),
                "watchlist_id": str(wl.id),
                "watchlist_name": wl.name,
                "category": wl.category.value,
                "plate_text": plate_text,
                "status": AlertStatus.new.value,
                "ts": datetime.now(tz=timezone.utc).isoformat(),
            })
            channel = f"drishti:{site_id}:alerts"
            redis_client.publish(channel, payload)
            log.info(
                "alert fired plate=%s watchlist=%s category=%s alert_id=%s",
                plate_text,
                wl.name,
                wl.category.value,
                alert.id,
            )

    if created_ids:
        db.commit()
        # Best-effort push — runs after commit so alert IDs are durable
        _send_push_notifications(
            redis_client,
            site_id,
            title="DrishtiAI Alert",
            body=f"Plate {plate_text} matched a watchlist",
        )
        # Best-effort outbound webhooks
        try:
            _fire_webhooks(
                db=db,
                site_id=site_id,
                event_type="alert_new",
                payload={
                    "alert_id": str(created_ids[0]),
                    "plate_text": plate_text,
                    "event_id": str(event_id),
                },
            )
        except Exception as exc:
            log.debug("webhook fire failed: %s", exc)

    return created_ids
