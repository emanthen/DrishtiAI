from drishtiai_worker.celery_app import app


@app.task(name="drishtiai_worker.tasks.reports.generate_daily_report")
def generate_daily_report(site_id: str, date: str) -> dict:
    # Phase 8: implement PDF/CSV report generation
    raise NotImplementedError("reports — Phase 8")


@app.task(name="drishtiai_worker.tasks.reports.generate_monthly_report")
def generate_monthly_report(site_id: str, month: str) -> dict:
    raise NotImplementedError("reports — Phase 8")
