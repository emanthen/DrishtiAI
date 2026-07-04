"""
Outbound webhook delivery for pipeline events.

Loads enabled Webhook rows for a site from Postgres, signs the payload
with HMAC-SHA256 if a secret is configured, and POSTs to each URL.
Failures are logged but never re-raised — webhooks are best-effort.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import urllib.request
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from drishtiai_shared.models.webhook import Webhook

log = logging.getLogger(__name__)

_TIMEOUT_S = 5
_USER_AGENT = "DrishtiAI-Webhook/1.0"


def fire(
    *,
    db: Session,
    site_id: uuid.UUID,
    event_type: str,
    payload: dict,
) -> None:
    """
    Fire all enabled webhooks for `site_id` that subscribe to `event_type`.
    `payload` is the JSON body (must be JSON-serialisable).
    """
    rows = list(db.scalars(
        select(Webhook).where(
            Webhook.site_id == site_id,
            Webhook.enabled.is_(True),
        )
    ).all())

    if not rows:
        return

    body = json.dumps({
        "event": event_type,
        "site_id": str(site_id),
        "ts": datetime.now(tz=timezone.utc).isoformat(),
        **payload,
    }, default=str).encode()

    for wh in rows:
        # Skip if this webhook doesn't subscribe to the event
        # (empty list = all events)
        if wh.events and event_type not in wh.events:
            continue
        _deliver(db=db, webhook=wh, body=body)


def _sign(secret: str, body: bytes) -> str:
    mac = hmac.new(secret.encode(), body, hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


def _deliver(*, db: Session, webhook: Webhook, body: bytes) -> None:
    headers = {
        "Content-Type": "application/json",
        "User-Agent": _USER_AGENT,
        "X-Drishti-Event-ID": str(uuid.uuid4()),
    }
    if webhook.secret:
        headers["X-Drishti-Signature"] = _sign(webhook.secret, body)

    status_code: int | None = None
    try:
        req = urllib.request.Request(
            webhook.url, data=body, headers=headers, method="POST"
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
            status_code = resp.status
        log.info("webhook delivered url=%s status=%s", webhook.url, status_code)
    except urllib.error.HTTPError as exc:
        status_code = exc.code
        log.warning("webhook HTTP error url=%s status=%s", webhook.url, exc.code)
    except Exception as exc:
        log.warning("webhook delivery failed url=%s error=%s", webhook.url, exc)
    finally:
        # Update last_triggered_at + last_status_code without touching other cols
        try:
            db.execute(
                update(Webhook)
                .where(Webhook.id == webhook.id)
                .values(
                    last_triggered_at=datetime.now(tz=timezone.utc),
                    last_status_code=status_code,
                )
            )
            db.commit()
        except Exception:
            db.rollback()
