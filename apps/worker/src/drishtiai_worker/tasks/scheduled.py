"""
Fan-out tasks called by Celery Beat.

Each function queries all active sites and dispatches per-site tasks
so the Beat scheduler only needs one entry per job type.
"""
import logging
import os
from datetime import date, timedelta

from sqlalchemy import create_engine, text

from drishtiai_worker.celery_app import app
from drishtiai_worker.tasks.reports import generate_daily_report
from drishtiai_worker.tasks.retention import enforce_retention_policy

log = logging.getLogger(__name__)

_DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://drishtiai:drishtiai@postgres:5432/drishtiai")


def _active_site_ids() -> list[str]:
    engine = create_engine(_DB_URL, pool_pre_ping=True)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id FROM sites WHERE is_active = true")).fetchall()
    return [str(r[0]) for r in rows]


@app.task(name="drishtiai_worker.tasks.scheduled.run_daily_reports")
def run_daily_reports() -> dict:
    """Fan out daily PDF report generation to all active sites (runs at 00:30 UTC)."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    site_ids = _active_site_ids()
    for sid in site_ids:
        generate_daily_report.apply_async(
            kwargs={"site_id": sid, "date_str": yesterday},
            queue="reports",
        )
    log.info("Dispatched daily reports for %d sites (date=%s)", len(site_ids), yesterday)
    return {"sites": len(site_ids), "date": yesterday}


@app.task(name="drishtiai_worker.tasks.scheduled.run_retention_all_sites")
def run_retention_all_sites() -> dict:
    """Fan out retention enforcement to all active sites (runs at 02:00 UTC)."""
    site_ids = _active_site_ids()
    for sid in site_ids:
        enforce_retention_policy.apply_async(
            kwargs={"site_id": sid},
            queue="retention",
        )
    log.info("Dispatched retention enforcement for %d sites", len(site_ids))
    return {"sites": len(site_ids)}
