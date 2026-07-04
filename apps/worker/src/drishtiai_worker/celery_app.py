import os
from celery import Celery
from celery.schedules import crontab

redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")

app = Celery("drishtiai", broker=redis_url, backend=redis_url)

app.config_from_object(
    {
        "task_serializer": "json",
        "result_serializer": "json",
        "accept_content": ["json"],
        "timezone": "UTC",
        "enable_utc": True,
        "task_track_started": True,
        "task_acks_late": True,
        "worker_prefetch_multiplier": 1,
        "task_routes": {
            "drishtiai_worker.tasks.reports.*":   {"queue": "reports"},
            "drishtiai_worker.tasks.retention.*": {"queue": "retention"},
            "drishtiai_worker.tasks.export.*":    {"queue": "export"},
            "drishtiai_worker.tasks.scheduled.*": {"queue": "celery"},
        },
        "beat_schedule": {
            # 00:30 UTC — generate yesterday's summary for all active sites
            "daily-reports": {
                "task": "drishtiai_worker.tasks.scheduled.run_daily_reports",
                "schedule": crontab(hour=0, minute=30),
            },
            # 02:00 UTC — purge expired data for all active sites
            "nightly-retention": {
                "task": "drishtiai_worker.tasks.scheduled.run_retention_all_sites",
                "schedule": crontab(hour=2, minute=0),
            },
        },
    }
)

app.autodiscover_tasks(["drishtiai_worker.tasks"])
