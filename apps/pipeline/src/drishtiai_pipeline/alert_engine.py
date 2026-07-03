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
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from drishtiai_shared.models.alert import Alert, AlertStatus
from drishtiai_shared.models.watchlist import Watchlist, WatchlistEntry, PlatePattern

log = logging.getLogger(__name__)


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

    return created_ids
