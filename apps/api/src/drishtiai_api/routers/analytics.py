"""
Analytics API — Phase 6.

All queries are time-bounded so they hit the events partition index.
Timezone note: groupings use the site's stored timezone via AT TIME ZONE
in Postgres; defaults to Asia/Kathmandu when not resolved.
"""
import uuid
import zoneinfo
from datetime import datetime, timezone, timedelta
from typing import Annotated

from fastapi import APIRouter, Query, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text, select, func

from drishtiai_shared.models.alert import Alert, AlertStatus
from drishtiai_shared.models.event import Event, EventKind
from drishtiai_shared.models.gate import GateController, GateTriggerLog
from drishtiai_shared.models.parking import ParkingSession
from drishtiai_shared.models.site import Site
from drishtiai_api.deps import CurrentUser, DbSession

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_site(
    site_id: uuid.UUID | None, current_user: CurrentUser, db: DbSession
) -> uuid.UUID:
    """Return the requested site_id, or the user's first site, or raise 422."""
    if site_id:
        return site_id
    if current_user.site_ids:
        return uuid.UUID(current_user.site_ids[0])
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="site_id required",
    )


_FALLBACK_TZ = "Asia/Kathmandu"
_VALID_TZ = zoneinfo.available_timezones()


def _site_tz(site_id: uuid.UUID, db: DbSession) -> str:
    site = db.get(Site, site_id)
    tz = (site.timezone if site else None) or _FALLBACK_TZ
    # Validate before embedding in SQL — rejects any non-IANA string
    return tz if tz in _VALID_TZ else _FALLBACK_TZ


def _today_start(tz: str) -> str:
    """Return ISO string for midnight today in the given timezone."""
    return f"now()::timestamptz AT TIME ZONE '{tz}'"  # used inline in SQL


# ── Overview ──────────────────────────────────────────────────────────────────

class OverviewOut(BaseModel):
    events_today: int
    active_sessions: int
    revenue_today: float
    open_alerts: int
    gate_triggers_today: int
    active_passes: int


@router.get("/overview", response_model=OverviewOut)
async def overview(
    current_user: CurrentUser,
    db: DbSession,
    site_id: Annotated[uuid.UUID | None, Query()] = None,
) -> OverviewOut:
    sid = _resolve_site(site_id, current_user, db)
    tz = _site_tz(sid, db)

    today_sql = f"DATE_TRUNC('day', NOW() AT TIME ZONE '{tz}') AT TIME ZONE '{tz}'"

    events_today: int = db.scalar(text(
        f"SELECT COUNT(*) FROM events "
        f"WHERE site_id = :sid AND kind = 'plate_read' AND ts >= {today_sql}"
    ), {"sid": sid}) or 0

    active_sessions: int = db.scalar(
        select(func.count(ParkingSession.id)).where(
            ParkingSession.site_id == sid,
            ParkingSession.exit_event_id.is_(None),
        )
    ) or 0

    revenue_today: float = db.scalar(text(
        f"SELECT COALESCE(SUM(amount_due), 0) FROM parking_sessions "
        f"WHERE site_id = :sid AND exit_event_id IS NOT NULL AND created_at >= {today_sql}"
    ), {"sid": sid}) or 0.0

    open_alerts: int = db.scalar(text(
        "SELECT COUNT(*) FROM alerts a "
        "JOIN events e ON a.event_id = e.id "
        "WHERE e.site_id = :sid AND a.status = 'new'"
    ), {"sid": sid}) or 0

    gate_triggers_today: int = db.scalar(text(
        f"SELECT COUNT(*) FROM gate_trigger_logs gl "
        f"JOIN gate_controllers gc ON gl.gate_controller_id = gc.id "
        f"WHERE gc.site_id = :sid AND gl.success = true AND gl.triggered_at >= {today_sql}"
    ), {"sid": sid}) or 0

    active_passes: int = db.scalar(text(
        "SELECT COUNT(*) FROM visitor_passes "
        "WHERE site_id = :sid AND used = false AND valid_from <= NOW() AND valid_to >= NOW()"
    ), {"sid": sid}) or 0

    return OverviewOut(
        events_today=events_today,
        active_sessions=active_sessions,
        revenue_today=float(revenue_today),
        open_alerts=open_alerts,
        gate_triggers_today=gate_triggers_today,
        active_passes=active_passes,
    )


# ── Hourly traffic ─────────────────────────────────────────────────────────────

class HourlyBucket(BaseModel):
    hour: int       # 0–23
    count: int


@router.get("/hourly-traffic", response_model=list[HourlyBucket])
async def hourly_traffic(
    current_user: CurrentUser,
    db: DbSession,
    site_id: Annotated[uuid.UUID | None, Query()] = None,
    days: Annotated[int, Query(ge=1, le=90)] = 7,
) -> list[HourlyBucket]:
    """Event counts grouped by hour-of-day, aggregated over the last N days."""
    sid = _resolve_site(site_id, current_user, db)
    tz = _site_tz(sid, db)

    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    rows = db.execute(text(
        f"SELECT EXTRACT(HOUR FROM ts AT TIME ZONE '{tz}')::int AS hour, COUNT(*)::int AS count "
        "FROM events "
        "WHERE site_id = :sid AND kind = 'plate_read' "
        "  AND ts >= :cutoff "
        "GROUP BY hour ORDER BY hour"
    ), {"sid": sid, "cutoff": cutoff}).all()

    by_hour = {r.hour: r.count for r in rows}
    return [HourlyBucket(hour=h, count=by_hour.get(h, 0)) for h in range(24)]


# ── Daily revenue ─────────────────────────────────────────────────────────────

class DailyRevenue(BaseModel):
    date: str       # YYYY-MM-DD
    revenue: float
    sessions: int


@router.get("/daily-revenue", response_model=list[DailyRevenue])
async def daily_revenue(
    current_user: CurrentUser,
    db: DbSession,
    site_id: Annotated[uuid.UUID | None, Query()] = None,
    days: Annotated[int, Query(ge=1, le=90)] = 14,
) -> list[DailyRevenue]:
    """Daily parking revenue and closed session count for the last N days."""
    sid = _resolve_site(site_id, current_user, db)
    tz = _site_tz(sid, db)

    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    rows = db.execute(text(
        f"SELECT (created_at AT TIME ZONE '{tz}')::date::text AS date, "
        "       COALESCE(SUM(amount_due), 0)::float AS revenue, "
        "       COUNT(*)::int AS sessions "
        "FROM parking_sessions "
        "WHERE site_id = :sid AND exit_event_id IS NOT NULL "
        "  AND created_at >= :cutoff "
        "GROUP BY date ORDER BY date"
    ), {"sid": sid, "cutoff": cutoff}).all()

    # Fill missing days with zeros
    today = datetime.now(tz=timezone.utc).date()
    by_date = {r.date: (float(r.revenue), r.sessions) for r in rows}
    result = []
    for i in range(days - 1, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        rev, ses = by_date.get(d, (0.0, 0))
        result.append(DailyRevenue(date=d, revenue=rev, sessions=ses))
    return result


# ── Occupancy trend (last 24 h) ───────────────────────────────────────────────

class OccupancyBucket(BaseModel):
    hour: str       # ISO datetime string, start of hour
    entries: int    # sessions that opened during this hour
    exits: int      # sessions that closed during this hour


@router.get("/occupancy", response_model=list[OccupancyBucket])
async def occupancy(
    current_user: CurrentUser,
    db: DbSession,
    site_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[OccupancyBucket]:
    """Entries and exits per hour over the last 24 hours."""
    sid = _resolve_site(site_id, current_user, db)

    entry_rows = db.execute(text(
        "SELECT DATE_TRUNC('hour', created_at)::text AS hour, COUNT(*)::int AS cnt "
        "FROM parking_sessions "
        "WHERE site_id = :sid AND created_at >= NOW() - INTERVAL '24 hours' "
        "GROUP BY hour ORDER BY hour"
    ), {"sid": sid}).all()

    exit_rows = db.execute(text(
        "SELECT DATE_TRUNC('hour', ps.updated_at)::text AS hour, COUNT(*)::int AS cnt "
        "FROM parking_sessions ps "
        "WHERE ps.site_id = :sid AND ps.exit_event_id IS NOT NULL "
        "  AND ps.updated_at >= NOW() - INTERVAL '24 hours' "
        "GROUP BY hour ORDER BY hour"
    ), {"sid": sid}).all()

    entries_by_hour = {r.hour: r.cnt for r in entry_rows}
    exits_by_hour = {r.hour: r.cnt for r in exit_rows}
    all_hours = sorted(set(entries_by_hour) | set(exits_by_hour))

    return [
        OccupancyBucket(
            hour=h,
            entries=entries_by_hour.get(h, 0),
            exits=exits_by_hour.get(h, 0),
        )
        for h in all_hours
    ]


# ── Top plates ────────────────────────────────────────────────────────────────

class TopPlate(BaseModel):
    plate_text: str
    count: int


@router.get("/top-plates", response_model=list[TopPlate])
async def top_plates(
    current_user: CurrentUser,
    db: DbSession,
    site_id: Annotated[uuid.UUID | None, Query()] = None,
    days: Annotated[int, Query(ge=1, le=90)] = 30,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[TopPlate]:
    """Most-seen plates in the last N days."""
    sid = _resolve_site(site_id, current_user, db)

    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    rows = db.execute(text(
        "SELECT p.text AS plate_text, COUNT(*)::int AS count "
        "FROM events e "
        "JOIN plates p ON e.plate_id = p.id "
        "WHERE e.site_id = :sid AND e.kind = 'plate_read' "
        "  AND e.ts >= :cutoff "
        "GROUP BY p.text ORDER BY count DESC LIMIT :lim"
    ), {"sid": sid, "cutoff": cutoff, "lim": limit}).all()

    return [TopPlate(plate_text=r.plate_text, count=r.count) for r in rows]
