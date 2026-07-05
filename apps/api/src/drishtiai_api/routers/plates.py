"""
Plate investigation endpoints.

All event queries are time-bounded to respect the partitioned events index.
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func, text
from sqlalchemy.orm import joinedload

from drishtiai_shared.models.camera import Camera
from drishtiai_shared.models.event import Event
from drishtiai_shared.models.plate import Plate
from drishtiai_api.deps import CurrentUser, DbSession

router = APIRouter()


# ── Models ────────────────────────────────────────────────────────────────────

class VehicleBadge(BaseModel):
    id: uuid.UUID
    color: str | None
    type: str | None
    first_seen: datetime | None
    last_seen: datetime | None


class PlateSearchResult(BaseModel):
    id: uuid.UUID
    text: str
    format_class: str
    vehicle: VehicleBadge | None = None


class TimelineEvent(BaseModel):
    id: uuid.UUID
    ts: datetime
    kind: str
    confidence: float | None
    camera_id: uuid.UUID
    camera_name: str | None
    snapshot_key: str | None


class TimelinePage(BaseModel):
    items: list[TimelineEvent]
    next_cursor: str | None


class CameraSighting(BaseModel):
    camera_id: str
    name: str
    count: int
    first_seen: datetime
    last_seen: datetime


# ── Search ────────────────────────────────────────────────────────────────────

@router.get("/search", response_model=list[PlateSearchResult])
async def search_plates(
    current_user: CurrentUser,
    db: DbSession,
    q: Annotated[str, Query(min_length=2, description="Partial plate text (trigram)")],
    site_id: Annotated[uuid.UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[PlateSearchResult]:
    """Trigram search for plates seen at a site, ordered by similarity."""
    sid = site_id or (uuid.UUID(current_user.site_ids[0]) if current_user.site_ids else None)

    plates_q = (
        select(Plate)
        .options(joinedload(Plate.vehicle))
        .where(Plate.text.op("%%")(q))
        .order_by(func.similarity(Plate.text, q).desc())
        .limit(limit)
    )

    if sid:
        plates_q = plates_q.where(
            Plate.id.in_(
                select(Event.plate_id)
                .where(Event.site_id == sid)
                .where(Event.plate_id.is_not(None))
            )
        )

    rows = list(db.scalars(plates_q).unique().all())
    results = []
    for p in rows:
        badge = None
        if p.vehicle:
            badge = VehicleBadge(
                id=p.vehicle.id,
                color=p.vehicle.color,
                type=p.vehicle.type,
                first_seen=p.vehicle.first_seen,
                last_seen=p.vehicle.last_seen,
            )
        results.append(PlateSearchResult(
            id=p.id,
            text=p.text,
            format_class=p.format_class.value if hasattr(p.format_class, "value") else str(p.format_class),
            vehicle=badge,
        ))
    return results


# ── Per-plate timeline ────────────────────────────────────────────────────────

@router.get("/{plate_id}/timeline", response_model=TimelinePage)
async def plate_timeline(
    plate_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    days: Annotated[int, Query(ge=1, le=90)] = 30,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    cursor: Annotated[str | None, Query()] = None,
) -> TimelinePage:
    """Events for a specific plate, newest first, time-bounded."""
    if db.get(Plate, plate_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plate not found")

    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)

    q = (
        select(Event)
        .options(joinedload(Event.camera))
        .where(Event.plate_id == plate_id)
        .where(Event.ts >= cutoff)
        .order_by(Event.ts.desc())
    )

    if cursor:
        try:
            q = q.where(Event.ts < datetime.fromisoformat(cursor))
        except ValueError:
            pass

    q = q.limit(limit + 1)
    rows = list(db.scalars(q).unique().all())

    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = rows[-1].ts.isoformat()

    items = [
        TimelineEvent(
            id=e.id,
            ts=e.ts,
            kind=e.kind.value if hasattr(e.kind, "value") else str(e.kind),
            confidence=e.confidence,
            camera_id=e.camera_id,
            camera_name=e.camera.name if e.camera else None,
            snapshot_key=e.snapshot_key,
        )
        for e in rows
    ]

    return TimelinePage(items=items, next_cursor=next_cursor)


# ── Cross-camera sightings ────────────────────────────────────────────────────

@router.get("/{plate_id}/camera-sightings", response_model=list[CameraSighting])
async def camera_sightings(
    plate_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    days: Annotated[int, Query(ge=1, le=90)] = 30,
) -> list[CameraSighting]:
    """Per-camera read count and first/last seen for a specific plate."""
    if db.get(Plate, plate_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plate not found")

    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)

    rows = db.execute(text(
        "SELECT c.id::text AS camera_id, c.name, "
        "       COUNT(e.id)::int AS count, "
        "       MIN(e.ts) AS first_seen, "
        "       MAX(e.ts) AS last_seen "
        "FROM events e "
        "JOIN cameras c ON c.id = e.camera_id "
        "WHERE e.plate_id = :plate_id AND e.ts >= :cutoff "
        "GROUP BY c.id, c.name ORDER BY count DESC"
    ), {"plate_id": plate_id, "cutoff": cutoff}).all()

    return [
        CameraSighting(
            camera_id=r.camera_id,
            name=r.name,
            count=r.count,
            first_seen=r.first_seen,
            last_seen=r.last_seen,
        )
        for r in rows
    ]
