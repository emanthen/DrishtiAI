"""
Retention enforcement task.

Reads RetentionPolicy rows for a site and purges data that has
exceeded its retention window:
  - plate_events: DELETE rows from `events` (+ Postgres CASCADE handles
    alerts/parking_session FK references)
  - snapshots: list + delete objects from MinIO snapshots bucket
  - clips: list + delete objects from MinIO clips bucket

Designed to run nightly via Celery Beat or an external cron.
"""
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

from minio import Minio
from sqlalchemy import create_engine, text

from drishtiai_worker.celery_app import app

log = logging.getLogger(__name__)

_DB_URL         = os.getenv("DATABASE_URL", "postgresql+psycopg://drishtiai:drishtiai@postgres:5432/drishtiai")
_MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
_MINIO_ACCESS   = os.getenv("MINIO_ACCESS_KEY", "drishtiai")
_MINIO_SECRET   = os.getenv("MINIO_SECRET_KEY", "drishtiai")
_MINIO_SECURE   = os.getenv("MINIO_SECURE", "false").lower() == "true"

# Default retention when no policy row exists for a data class
_DEFAULTS = {
    "plate_events": 90,
    "snapshots":    30,
    "clips":        14,
    "audit_logs":  365,
}


def _engine():
    return create_engine(_DB_URL, pool_pre_ping=True)


def _minio() -> Minio:
    return Minio(_MINIO_ENDPOINT, access_key=_MINIO_ACCESS,
                 secret_key=_MINIO_SECRET, secure=_MINIO_SECURE)


def _cutoff(retain_days: int) -> datetime:
    return datetime.now(tz=timezone.utc) - timedelta(days=retain_days)


@app.task(name="drishtiai_worker.tasks.retention.enforce_retention_policy")
def enforce_retention_policy(site_id: str) -> dict:
    """
    Enforce all retention policies for `site_id`.
    Returns dict with counts of deleted records per data class.
    """
    sid = uuid.UUID(site_id)
    engine = _engine()
    mc = _minio()
    results: dict[str, int] = {}

    with engine.connect() as conn:
        # Load site-specific policies
        rows = conn.execute(text(
            "SELECT data_class, retain_days FROM retention_policies WHERE site_id = :sid"
        ), {"sid": sid}).fetchall()
        policies = {r.data_class: r.retain_days for r in rows}

    # ── plate_events ──────────────────────────────────────────────────────────
    retain_days = policies.get("plate_events", _DEFAULTS["plate_events"])
    cutoff = _cutoff(retain_days)
    with engine.begin() as conn:
        result = conn.execute(text("""
            DELETE FROM events
            WHERE site_id = :sid
              AND ts < :cutoff
              AND kind = 'plate_read'
        """), {"sid": sid, "cutoff": cutoff})
        deleted = result.rowcount
    results["plate_events"] = deleted
    log.info("Retention: deleted %d plate_events for site %s (cutoff %s)", deleted, sid, cutoff.date())

    # ── snapshots (MinIO) ─────────────────────────────────────────────────────
    retain_days = policies.get("snapshots", _DEFAULTS["snapshots"])
    cutoff = _cutoff(retain_days)
    snap_deleted = _purge_minio_prefix(mc, "snapshots", f"{site_id}/", cutoff)
    results["snapshots"] = snap_deleted
    log.info("Retention: deleted %d snapshot objects for site %s", snap_deleted, sid)

    # ── clips (MinIO) ─────────────────────────────────────────────────────────
    retain_days = policies.get("clips", _DEFAULTS["clips"])
    cutoff = _cutoff(retain_days)
    clip_deleted = _purge_minio_prefix(mc, "clips", f"{site_id}/", cutoff)
    results["clips"] = clip_deleted
    log.info("Retention: deleted %d clip objects for site %s", clip_deleted, sid)

    return {"site_id": site_id, "deleted": results}


def _purge_minio_prefix(mc: Minio, bucket: str, prefix: str, cutoff: datetime) -> int:
    """Delete objects in `bucket` under `prefix` whose last_modified < cutoff."""
    try:
        objects = mc.list_objects(bucket, prefix=prefix, recursive=True)
    except Exception as exc:
        log.warning("MinIO list_objects failed for %s/%s: %s", bucket, prefix, exc)
        return 0

    to_delete = []
    for obj in objects:
        if obj.last_modified and obj.last_modified.replace(tzinfo=timezone.utc) < cutoff:
            to_delete.append(obj.object_name)

    count = 0
    for key in to_delete:
        try:
            mc.remove_object(bucket, key)
            count += 1
        except Exception as exc:
            log.warning("Failed to delete %s/%s: %s", bucket, key, exc)

    return count
