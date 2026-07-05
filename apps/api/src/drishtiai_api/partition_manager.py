"""
Partition manager for the events table.

events is PARTITION BY RANGE (ts) monthly.
All operations are idempotent (CREATE/DROP IF NOT EXISTS).
"""
from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)


def _bounds(year: int, month: int) -> tuple[str, str]:
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return start.isoformat(), end.isoformat()


def _offset(year: int, month: int, delta: int) -> tuple[int, int]:
    month += delta
    while month <= 0:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return year, month


def ensure_partitions(db: Session, ahead: int = 3, behind: int = 1) -> list[str]:
    """Idempotently create monthly partitions for ±months around today."""
    today = date.today()
    created: list[str] = []
    for delta in range(-behind, ahead + 1):
        y, m = _offset(today.year, today.month, delta)
        name = f"events_{y}_{m:02d}"
        start, end = _bounds(y, m)
        try:
            db.execute(text(
                f"CREATE TABLE IF NOT EXISTS {name} "
                f"PARTITION OF events FOR VALUES FROM ('{start}') TO ('{end}')"
            ))
            db.commit()
            created.append(name)
        except Exception as exc:
            db.rollback()
            log.warning("Could not create partition %s: %s", name, exc)
    return created


def list_partitions(db: Session) -> list[dict]:
    """Return event partitions with row estimates from pg_class, ordered by name."""
    rows = db.execute(text("""
        SELECT
            c.relname AS name,
            pg_get_expr(c.relpartbound, c.oid) AS bounds,
            greatest(c.reltuples::bigint, 0) AS row_estimate
        FROM pg_inherits i
        JOIN pg_class p ON p.oid = i.inhparent
        JOIN pg_class c ON c.oid = i.inhrelid
        WHERE p.relname = 'events'
        ORDER BY c.relname
    """)).all()
    return [{"name": r.name, "bounds": r.bounds, "row_estimate": r.row_estimate} for r in rows]


def drop_old_partitions(db: Session, older_than_months: int = 12) -> list[str]:
    """DROP monthly event partitions older than older_than_months. Never touches events_default."""
    today = date.today()
    ty, tm = _offset(today.year, today.month, -older_than_months)
    threshold = f"events_{ty}_{tm:02d}"

    dropped: list[str] = []
    for p in list_partitions(db):
        name = p["name"]
        # Only touch YYYY_MM shaped partitions, skip events_default and anything non-standard
        if len(name) != len("events_YYYY_MM") or not name.startswith("events_"):
            continue
        if name < threshold:
            try:
                db.execute(text(f"DROP TABLE IF EXISTS {name}"))
                db.commit()
                dropped.append(name)
                log.info("Dropped old event partition %s", name)
            except Exception as exc:
                db.rollback()
                log.warning("Could not drop partition %s: %s", name, exc)
    return dropped
