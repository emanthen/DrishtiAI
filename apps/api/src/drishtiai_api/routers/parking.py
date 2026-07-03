import math
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func

from drishtiai_shared.models.parking import ParkingSession, PaymentStatus, Tariff
from drishtiai_shared.models.plate import Plate
from drishtiai_shared.models.event import Event
from drishtiai_api.deps import CurrentUser, DbSession


def _compute_charge(duration_s: int, rules: dict) -> float:
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
            if min(minutes, tier_limit) - prev_limit > 0:
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

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────

class ParkingSessionOut(BaseModel):
    id: uuid.UUID
    site_id: uuid.UUID
    plate_id: uuid.UUID | None
    entry_event_id: uuid.UUID | None
    exit_event_id: uuid.UUID | None
    duration_s: int | None
    amount_due: float | None
    payment_status: PaymentStatus
    created_at: datetime
    # denormalised
    plate_text: str | None = None
    entry_ts: datetime | None = None
    exit_ts: datetime | None = None

    model_config = {"from_attributes": True}


class ParkingPage(BaseModel):
    items: list[ParkingSessionOut]
    total: int
    next_cursor: str | None


class CloseBody(BaseModel):
    notes: str | None = None


class MarkPaidBody(BaseModel):
    notes: str | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _enrich(session: ParkingSession, db: DbSession) -> ParkingSessionOut:
    out = ParkingSessionOut.model_validate(session)
    plate = db.get(Plate, session.plate_id) if session.plate_id else None
    out.plate_text = plate.text if plate else None
    if session.entry_event_id:
        entry_ev = db.get(Event, session.entry_event_id)
        out.entry_ts = entry_ev.ts if entry_ev else None
    if session.exit_event_id:
        exit_ev = db.get(Event, session.exit_event_id)
        out.exit_ts = exit_ev.ts if exit_ev else None
    return out


def _get_or_404(session_id: uuid.UUID, db: DbSession) -> ParkingSession:
    s = db.get(ParkingSession, session_id)
    if s is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return s


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=ParkingPage)
async def list_sessions(
    current_user: CurrentUser,
    db: DbSession,
    site_id: Annotated[uuid.UUID | None, Query()] = None,
    active_only: Annotated[bool, Query()] = False,
    payment_status: Annotated[PaymentStatus | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: Annotated[str | None, Query()] = None,
) -> ParkingPage:
    q = select(ParkingSession)
    if site_id:
        q = q.where(ParkingSession.site_id == site_id)
    elif current_user.site_ids:
        q = q.where(ParkingSession.site_id.in_(current_user.site_ids))
    if active_only:
        q = q.where(ParkingSession.exit_event_id.is_(None))
    if payment_status:
        q = q.where(ParkingSession.payment_status == payment_status)
    if cursor:
        try:
            q = q.where(ParkingSession.created_at < datetime.fromisoformat(cursor))
        except ValueError:
            pass

    q = q.order_by(ParkingSession.created_at.desc()).limit(limit + 1)
    rows = list(db.scalars(q).all())

    items = [_enrich(s, db) for s in rows[:limit]]
    next_cursor = items[-1].created_at.isoformat() if len(rows) > limit else None

    total = db.scalar(select(func.count(ParkingSession.id))) or 0
    return ParkingPage(items=items, total=total, next_cursor=next_cursor)


@router.get("/active", response_model=list[ParkingSessionOut])
async def list_active(
    current_user: CurrentUser,
    db: DbSession,
    site_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[ParkingSessionOut]:
    """All currently open sessions (no exit event), newest first."""
    q = select(ParkingSession).where(ParkingSession.exit_event_id.is_(None))
    if site_id:
        q = q.where(ParkingSession.site_id == site_id)
    elif current_user.site_ids:
        q = q.where(ParkingSession.site_id.in_(current_user.site_ids))
    q = q.order_by(ParkingSession.created_at.desc())
    return [_enrich(s, db) for s in db.scalars(q).all()]


@router.get("/{session_id}", response_model=ParkingSessionOut)
async def get_session(
    session_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> ParkingSessionOut:
    return _enrich(_get_or_404(session_id, db), db)


# ── Actions ───────────────────────────────────────────────────────────────────

@router.post("/{session_id}/close", response_model=ParkingSessionOut)
async def close_session(
    session_id: uuid.UUID, body: CloseBody, current_user: CurrentUser, db: DbSession
) -> ParkingSessionOut:
    """Manually close an open session (e.g. exit camera missed the plate)."""
    s = _get_or_404(session_id, db)
    if s.exit_event_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Session already closed"
        )

    now = datetime.now(tz=timezone.utc)

    # Compute duration from entry event ts
    duration_s = 0
    if s.entry_event_id:
        entry_ev = db.get(Event, s.entry_event_id)
        if entry_ev:
            duration_s = int((now - entry_ev.ts).total_seconds())

    tariff = db.scalars(
        select(Tariff)
        .where(Tariff.site_id == s.site_id, Tariff.active == True)  # noqa: E712
        .order_by(Tariff.created_at.desc())
        .limit(1)
    ).first()

    s.duration_s = duration_s
    s.tariff_snapshot = tariff.rules_json if tariff else None
    s.amount_due = _compute_charge(duration_s, tariff.rules_json) if tariff else 0.0
    db.commit()
    db.refresh(s)
    return _enrich(s, db)


@router.post("/{session_id}/mark-paid", response_model=ParkingSessionOut)
async def mark_paid(
    session_id: uuid.UUID, body: MarkPaidBody, current_user: CurrentUser, db: DbSession
) -> ParkingSessionOut:
    s = _get_or_404(session_id, db)
    s.payment_status = PaymentStatus.paid
    db.commit()
    db.refresh(s)
    return _enrich(s, db)


@router.post("/{session_id}/waive", response_model=ParkingSessionOut)
async def waive_session(
    session_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> ParkingSessionOut:
    s = _get_or_404(session_id, db)
    s.payment_status = PaymentStatus.waived
    s.amount_due = 0.0
    db.commit()
    db.refresh(s)
    return _enrich(s, db)
