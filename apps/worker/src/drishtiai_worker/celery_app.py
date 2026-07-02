import os
from celery import Celery

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
            "drishtiai_worker.tasks.reports.*": {"queue": "reports"},
            "drishtiai_worker.tasks.retention.*": {"queue": "retention"},
            "drishtiai_worker.tasks.export.*": {"queue": "export"},
        },
    }
)

app.autodiscover_tasks(["drishtiai_worker.tasks"])
