"""
Parking session lifecycle manager — Phase 3.

Called after every committed plate_read event for entry/exit cameras.
Uses camera.role to decide direction:
  - parking_entry → open a new ParkingSession
  - parking_exit  → close the open session and apply the site tariff

Open sessions are tracked in Redis:
  key: parking:open:{site_id}:{plate_norm} → JSON {session_id, entry_ts}
  TTL: 24 h (dangling key expiry for vehicles that never exit)
"""
from __future__ import annotations

import json
import logging
import math
import uuid
from datetime import datetime, timezone

import redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from drishtiai_shared.models.camera import CameraRole
from drishtiai_shared.models.event import Event
from drishtiai_shared.models.parking import ParkingSession, PaymentStatus, Tariff

log = logging.getLogger(__name__)

_OPEN_SESSION_TTL_S = 24 * 3600


def _redis_key(site_id: uuid.UUID, plate_norm: str) -> str:
    return f"parking:open:{site_id}:{plate_norm}"


def _normalise(plate_text: str) -> str:
    return plate_text.upper().replace(" ", "").replace("-", "")


def _compute_charge(duration_s: int, rules: dict) -> float:
    """Apply tiered tariff rules, return charge amount (in rules currency)."""
    minutes = duration_s / 60
    grace = float(rules.get("grace_minutes", 0))
    if minutes <= grace:
        return 0.0

    tiers = rules.get("tiers", [])
    charge = 0.0
    prev_limit = 0.0

    for tier in tiers:
        if "up_to_minutes" in tier:
            tier_limit = float(tier["up_to_minutes"])
            applicable = min(minutes, tier_limit) - prev_limit
            if applicable > 0:
                charge += float(tier.get("charge", 0))
            prev_limit = tier_limit
            if minutes <= tier_limit:
                break
        elif "per_hour" in tier:
            remaining = minutes - prev_limit
            if remaining > 0:
                hours = math.ceil(remaining / 60)
                hourly = float(tier["per_hour"]) * hours
                max_pd = tier.get("max_per_day")
                if max_pd is not None:
                    hourly = min(hourly, float(max_pd))
                charge += hourly
            break

    return charge


def on_plate_read(
    *,
    db: Session,
    r: redis.Redis,
    site_id: uuid.UUID,
    event_id: uuid.UUID,
    plate_text: str,
    camera_role: CameraRole,
) -> None:
    """Dispatch to open/close based on camera role. No-op for non-parking roles."""
    if camera_role == CameraRole.parking_entry:
        _open_session(db=db, r=r, site_id=site_id, event_id=event_id, plate_text=plate_text)
    elif camera_role == CameraRole.parking_exit:
        _close_session(db=db, r=r, site_id=site_id, event_id=event_id, plate_text=plate_text)


def _open_session(
    *,
    db: Session,
    r: redis.Redis,
    site_id: uuid.UUID,
    event_id: uuid.UUID,
    plate_text: str,
) -> None:
    plate_norm = _normalise(plate_text)
    key = _redis_key(site_id, plate_norm)

    if r.exists(key):
        log.debug("parking: session already open for %s — ignoring duplicate entry", plate_text)
        return

    event = db.get(Event, event_id)
    plate_id = event.plate_id if event else None

    session = ParkingSession(
        id=uuid.uuid4(),
        site_id=site_id,
        plate_id=plate_id,
        entry_event_id=event_id,
        payment_status=PaymentStatus.pending,
    )
    db.add(session)
    db.commit()

    entry_ts = datetime.now(tz=timezone.utc).isoformat()
    r.setex(key, _OPEN_SESSION_TTL_S, json.dumps({
        "session_id": str(session.id),
        "plate_text": plate_text,
        "entry_ts": entry_ts,
    }))

    r.publish(f"drishti:{site_id}:parking", json.dumps({
        "event": "session_opened",
        "session_id": str(session.id),
        "plate_text": plate_text,
        "site_id": str(site_id),
        "entry_ts": entry_ts,
    }))
    log.info("parking: opened session_id=%s plate=%s", session.id, plate_text)


def _close_session(
    *,
    db: Session,
    r: redis.Redis,
    site_id: uuid.UUID,
    event_id: uuid.UUID,
    plate_text: str,
) -> None:
    plate_norm = _normalise(plate_text)
    key = _redis_key(site_id, plate_norm)

    raw = r.get(key)
    if raw is None:
        log.warning("parking: exit for %s but no open session found", plate_text)
        return

    data = json.loads(raw)
    session_id = uuid.UUID(data["session_id"])
    entry_ts = datetime.fromisoformat(data["entry_ts"])

    session = db.get(ParkingSession, session_id)
    if session is None:
        log.warning("parking: session %s not found in DB", session_id)
        r.delete(key)
        return

    now = datetime.now(tz=timezone.utc)
    duration_s = int((now - entry_ts).total_seconds())

    tariff = db.scalars(
        select(Tariff)
        .where(Tariff.site_id == site_id, Tariff.active == True)  # noqa: E712
        .order_by(Tariff.created_at.desc())
        .limit(1)
    ).first()

    amount_due = 0.0
    tariff_snapshot = None
    if tariff:
        tariff_snapshot = tariff.rules_json
        amount_due = _compute_charge(duration_s, tariff.rules_json)

    session.exit_event_id = event_id
    session.duration_s = duration_s
    session.tariff_snapshot = tariff_snapshot
    session.amount_due = amount_due
    db.commit()

    r.delete(key)

    r.publish(f"drishti:{site_id}:parking", json.dumps({
        "event": "session_closed",
        "session_id": str(session_id),
        "plate_text": plate_text,
        "site_id": str(site_id),
        "duration_s": duration_s,
        "amount_due": amount_due,
        "exit_ts": now.isoformat(),
    }))
    log.info(
        "parking: closed session_id=%s plate=%s duration=%ds amount=%.2f",
        session_id, plate_text, duration_s, amount_due,
    )
