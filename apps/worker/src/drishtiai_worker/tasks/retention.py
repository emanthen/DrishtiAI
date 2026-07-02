from drishtiai_worker.celery_app import app


@app.task(name="drishtiai_worker.tasks.retention.enforce_retention_policy")
def enforce_retention_policy(site_id: str) -> dict:
    # Phase 10: delete events/snapshots/clips past their retention date
    raise NotImplementedError("retention — Phase 10")
