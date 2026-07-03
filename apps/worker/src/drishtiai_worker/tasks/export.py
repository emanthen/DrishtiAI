"""
Async CSV export task — for large exports (>50 k rows) that would
block the API request.  Generates the file, uploads to MinIO
exports bucket, and returns a pre-signed URL valid for 24 h.
"""
import csv
import io
import os
import uuid
from datetime import date, datetime, timedelta, timezone

from minio import Minio
from sqlalchemy import create_engine, text

from drishtiai_worker.celery_app import app

_DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://drishtiai:drishtiai@postgres:5432/drishtiai")
_MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
_MINIO_ACCESS   = os.getenv("MINIO_ACCESS_KEY", "drishtiai")
_MINIO_SECRET   = os.getenv("MINIO_SECRET_KEY", "drishtiai")
_MINIO_SECURE   = os.getenv("MINIO_SECURE", "false").lower() == "true"
_BUCKET         = "exports"
_PRESIGN_HOURS  = 24


def _engine():
    return create_engine(_DB_URL, pool_pre_ping=True)


def _minio() -> Minio:
    return Minio(_MINIO_ENDPOINT, access_key=_MINIO_ACCESS,
                 secret_key=_MINIO_SECRET, secure=_MINIO_SECURE)


def _upload_csv(rows: list[list], headers: list[str], key: str) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    writer.writerows(rows)
    data = buf.getvalue().encode()
    mc = _minio()
    mc.put_object(_BUCKET, key, io.BytesIO(data), len(data), content_type="text/csv")
    url = mc.presigned_get_object(_BUCKET, key, expires=timedelta(hours=_PRESIGN_HOURS))
    return url


def _to_utc(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


@app.task(name="drishtiai_worker.tasks.export.export_events_csv")
def export_events_csv(site_id: str, from_date: str, to_date: str) -> dict:
    """Generate events CSV, upload to MinIO, return pre-signed URL."""
    from_ts = _to_utc(date.fromisoformat(from_date))
    to_ts   = _to_utc(date.fromisoformat(to_date) + timedelta(days=1))
    sid = uuid.UUID(site_id)

    engine = _engine()
    with engine.connect() as conn:
        rows_db = conn.execute(text("""
            SELECT e.ts AT TIME ZONE 'UTC', e.kind, p.text, c.name, e.confidence, e.id
            FROM events e
            LEFT JOIN plates p ON p.id = e.plate_id
            LEFT JOIN cameras c ON c.id = e.camera_id
            WHERE e.ts >= :from_ts AND e.ts < :to_ts AND e.site_id = :sid
            ORDER BY e.ts DESC LIMIT 200000
        """), {"from_ts": from_ts, "to_ts": to_ts, "sid": sid}).fetchall()

    data = [[str(r[0]), r[1], r[2] or "", r[3] or "", r[4] or "", str(r[5])] for r in rows_db]
    key = f"exports/{site_id}/events_{from_date}_{to_date}_{uuid.uuid4().hex[:6]}.csv"
    url = _upload_csv(data, ["timestamp", "kind", "plate", "camera", "confidence", "event_id"], key)
    return {"url": url, "rows": len(data), "key": key}


@app.task(name="drishtiai_worker.tasks.export.export_parking_csv")
def export_parking_csv(site_id: str, from_date: str, to_date: str) -> dict:
    """Generate parking sessions CSV, upload to MinIO, return pre-signed URL."""
    from_ts = _to_utc(date.fromisoformat(from_date))
    to_ts   = _to_utc(date.fromisoformat(to_date) + timedelta(days=1))
    sid = uuid.UUID(site_id)

    engine = _engine()
    with engine.connect() as conn:
        rows_db = conn.execute(text("""
            SELECT ps.created_at AT TIME ZONE 'UTC', ps.updated_at AT TIME ZONE 'UTC',
                   p.text, ps.duration_s, ps.amount_due, ps.payment_status, ps.id
            FROM parking_sessions ps
            LEFT JOIN plates p ON p.id = ps.plate_id
            WHERE ps.created_at >= :from_ts AND ps.created_at < :to_ts AND ps.site_id = :sid
            ORDER BY ps.created_at DESC LIMIT 100000
        """), {"from_ts": from_ts, "to_ts": to_ts, "sid": sid}).fetchall()

    data = [
        [str(r[0]), str(r[1]) if r[1] else "", r[2] or "",
         r[3] or "", f"{r[4]:.2f}" if r[4] is not None else "", r[5], str(r[6])]
        for r in rows_db
    ]
    key = f"exports/{site_id}/parking_{from_date}_{to_date}_{uuid.uuid4().hex[:6]}.csv"
    url = _upload_csv(data, ["entry_time","exit_time","plate","duration_s","amount_NPR","payment_status","session_id"], key)
    return {"url": url, "rows": len(data), "key": key}
