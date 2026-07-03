import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func

from drishtiai_shared.models.alert import Alert, AlertStatus
from drishtiai_shared.models.event import Event
from drishtiai_shared.models.plate import Plate
from drishtiai_shared.models.watchlist import Watchlist
from drishtiai_api.deps import CurrentUser, DbSession

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────

class AlertOut(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    watchlist_id: uuid.UUID | None
    status: AlertStatus
    ack_by: uuid.UUID | None
    ack_at: datetime | None
    snooze_until: datetime | None
    notes: str | None
    created_at: datetime
    # Denormalised for convenience
    plate_text: str | None = None
    camera_id: uuid.UUID | None = None
    site_id: uuid.UUID | None = None
    watchlist_name: str | None = None

    model_config = {"from_attributes": True}


class AlertsPage(BaseModel):
    items: list[AlertOut]
    total: int
    next_cursor: str | None


class AckBody(BaseModel):
    notes: str | None = None


class SnoozeBody(BaseModel):
    snooze_until: datetime
    notes: str | None = None


class ResolveBody(BaseModel):
    notes: str | None = None


# ── List ───────────────────────────────────────────────────────────────────────

@router.get("", response_model=AlertsPage)
async def list_alerts(
    current_user: CurrentUser,
    db: DbSession,
    site_id: Annotated[uuid.UUID | None, Query()] = None,
    alert_status: Annotated[AlertStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: Annotated[str | None, Query()] = None,
) -> AlertsPage:
    q = (
        select(Alert, Event, Plate, Watchlist)
        .join(Event, Alert.event_id == Event.id)
        .outerjoin(Plate, Event.plate_id == Plate.id)
        .outerjoin(Watchlist, Alert.watchlist_id == Watchlist.id)
    )
    if site_id:
        q = q.where(Event.site_id == site_id)
    elif current_user.site_ids:
        q = q.where(Event.site_id.in_(current_user.site_ids))
    if alert_status:
        q = q.where(Alert.status == alert_status)
    if cursor:
        try:
            cursor_dt = datetime.fromisoformat(cursor)
            q = q.where(Alert.created_at < cursor_dt)
        except ValueError:
            pass

    q = q.order_by(Alert.created_at.desc()).limit(limit + 1)
    rows = db.execute(q).all()

    items: list[AlertOut] = []
    for alert, event, plate, watchlist in rows[:limit]:
        out = AlertOut.model_validate(alert)
        out.plate_text = plate.text if plate else None
        out.camera_id = event.camera_id
        out.site_id = event.site_id
        out.watchlist_name = watchlist.name if watchlist else None
        items.append(out)

    next_cursor = None
    if len(rows) > limit:
        next_cursor = items[-1].created_at.isoformat()

    total = db.scalar(
        select(func.count(Alert.id)).select_from(
            q.subquery()
        )
    ) or 0

    return AlertsPage(items=items, total=total, next_cursor=next_cursor)


@router.get("/counts")
async def alert_counts(
    current_user: CurrentUser,
    db: DbSession,
    site_id: Annotated[uuid.UUID | None, Query()] = None,
) -> dict:
    """Return count of alerts per status — used for dashboard badge."""
    q = select(Alert.status, func.count(Alert.id)).join(Event, Alert.event_id == Event.id)
    if site_id:
        q = q.where(Event.site_id == site_id)
    elif current_user.site_ids:
        q = q.where(Event.site_id.in_(current_user.site_ids))
    q = q.group_by(Alert.status)
    rows = db.execute(q).all()
    counts = {s.value: 0 for s in AlertStatus}
    for row_status, count in rows:
        counts[row_status.value] = count
    counts["total_new"] = counts.get("new", 0)
    return counts


# ── Single alert ───────────────────────────────────────────────────────────────

def _get_alert_or_404(alert_id: uuid.UUID, db: DbSession) -> Alert:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return alert


@router.get("/{alert_id}", response_model=AlertOut)
async def get_alert(alert_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> AlertOut:
    alert = _get_alert_or_404(alert_id, db)
    event = db.get(Event, alert.event_id)
    plate = db.get(Plate, event.plate_id) if event and event.plate_id else None
    watchlist = db.get(Watchlist, alert.watchlist_id) if alert.watchlist_id else None
    out = AlertOut.model_validate(alert)
    out.plate_text = plate.text if plate else None
    out.camera_id = event.camera_id if event else None
    out.site_id = event.site_id if event else None
    out.watchlist_name = watchlist.name if watchlist else None
    return out


@router.post("/{alert_id}/ack", response_model=AlertOut)
async def ack_alert(
    alert_id: uuid.UUID, body: AckBody, current_user: CurrentUser, db: DbSession
) -> AlertOut:
    alert = _get_alert_or_404(alert_id, db)
    alert.status = AlertStatus.ack
    alert.ack_by = current_user.id
    alert.ack_at = datetime.now(tz=timezone.utc)
    if body.notes:
        alert.notes = body.notes
    db.commit()
    db.refresh(alert)
    return await get_alert(alert_id, current_user, db)


@router.post("/{alert_id}/snooze", response_model=AlertOut)
async def snooze_alert(
    alert_id: uuid.UUID, body: SnoozeBody, current_user: CurrentUser, db: DbSession
) -> AlertOut:
    alert = _get_alert_or_404(alert_id, db)
    alert.status = AlertStatus.snoozed
    alert.snooze_until = body.snooze_until
    if body.notes:
        alert.notes = body.notes
    db.commit()
    db.refresh(alert)
    return await get_alert(alert_id, current_user, db)


@router.post("/{alert_id}/resolve", response_model=AlertOut)
async def resolve_alert(
    alert_id: uuid.UUID, body: ResolveBody, current_user: CurrentUser, db: DbSession
) -> AlertOut:
    alert = _get_alert_or_404(alert_id, db)
    alert.status = AlertStatus.resolved
    if body.notes:
        alert.notes = body.notes
    db.commit()
    db.refresh(alert)
    return await get_alert(alert_id, current_user, db)
