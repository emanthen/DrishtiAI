import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.orm import joinedload

from drishtiai_shared.models.event import Event, EventKind
from drishtiai_shared.models.plate import Plate
from drishtiai_shared.models.vehicle import Vehicle
from drishtiai_api.deps import CurrentUser, DbSession
from drishtiai_api.storage import get_presigned_url

router = APIRouter()


class PlateOut(BaseModel):
    id: uuid.UUID
    text: str
    region: str | None
    format_class: str

    model_config = {"from_attributes": True}


class VehicleOut(BaseModel):
    id: uuid.UUID
    type: str | None
    color: str | None
    make: str | None
    model: str | None

    model_config = {"from_attributes": True}


class EventOut(BaseModel):
    id: uuid.UUID
    site_id: uuid.UUID
    camera_id: uuid.UUID
    ts: datetime
    kind: EventKind
    vehicle_id: uuid.UUID | None
    plate_id: uuid.UUID | None
    snapshot_key: str | None
    clip_key: str | None
    confidence: float | None
    plate: PlateOut | None = None
    vehicle: VehicleOut | None = None

    model_config = {"from_attributes": True}


class EventsPage(BaseModel):
    items: list[EventOut]
    next_cursor: str | None


@router.get("", response_model=EventsPage)
async def list_events(
    current_user: CurrentUser,
    db: DbSession,
    site_id: Annotated[uuid.UUID | None, Query()] = None,
    camera_id: Annotated[uuid.UUID | None, Query()] = None,
    kind: Annotated[EventKind | None, Query()] = None,
    from_ts: Annotated[datetime | None, Query(alias="from")] = None,
    to_ts: Annotated[datetime | None, Query(alias="to")] = None,
    plate: Annotated[str | None, Query(description="Partial plate search (trigram)")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    cursor: Annotated[str | None, Query()] = None,
) -> EventsPage:
    q = (
        select(Event)
        .options(joinedload(Event.plate), joinedload(Event.vehicle))
        .order_by(Event.ts.desc())
    )

    filters = []
    if site_id:
        filters.append(Event.site_id == site_id)
    if camera_id:
        filters.append(Event.camera_id == camera_id)
    if kind:
        filters.append(Event.kind == kind)
    if from_ts:
        filters.append(Event.ts >= from_ts)
    if to_ts:
        filters.append(Event.ts <= to_ts)

    if plate:
        # Fuzzy/partial plate search via pg_trgm
        q = q.join(Event.plate).where(
            Plate.text.op("%%")(plate)  # %% escapes to % in SQL — the trgm similarity operator
        )

    if cursor:
        # cursor is the ISO timestamp of the last item
        try:
            cursor_ts = datetime.fromisoformat(cursor)
            filters.append(Event.ts < cursor_ts)
        except ValueError:
            pass

    if filters:
        q = q.where(and_(*filters))

    q = q.limit(limit + 1)
    rows = list(db.scalars(q).unique().all())

    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = rows[-1].ts.isoformat()

    return EventsPage(items=rows, next_cursor=next_cursor)  # type: ignore[arg-type]


@router.get("/{event_id}", response_model=EventOut)
async def get_event(event_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> Event:
    event = db.scalar(
        select(Event)
        .options(joinedload(Event.plate), joinedload(Event.vehicle))
        .where(Event.id == event_id)
    )
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return event  # type: ignore[return-value]


@router.get("/{event_id}/snapshot")
async def get_snapshot(event_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> RedirectResponse:
    event = db.get(Event, event_id)
    if event is None or event.snapshot_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found")
    url = await get_presigned_url("snapshots", event.snapshot_key)
    return RedirectResponse(url=url, status_code=302)


@router.get("/{event_id}/clip")
async def get_clip(event_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> RedirectResponse:
    event = db.get(Event, event_id)
    if event is None or event.clip_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found")
    url = await get_presigned_url("clips", event.clip_key)
    return RedirectResponse(url=url, status_code=302)
