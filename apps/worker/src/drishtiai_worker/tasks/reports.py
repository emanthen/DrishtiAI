"""
Scheduled report generation tasks.

generate_daily_report — builds a PDF daily summary and stores it in
MinIO exports bucket under reports/{site_id}/{date}/daily_summary.pdf.
Returns a pre-signed URL valid for 7 days.

Schedule via Celery Beat or a cron job that calls:
    generate_daily_report.delay(site_id=str(site.id), date="2026-07-03")
"""
import io
import os
import uuid
from datetime import date, datetime, timedelta, timezone

from minio import Minio
from sqlalchemy import create_engine, text

from drishtiai_worker.celery_app import app

_DB_URL       = os.getenv("DATABASE_URL", "postgresql+psycopg://drishtiai:drishtiai@postgres:5432/drishtiai")
_MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
_MINIO_ACCESS   = os.getenv("MINIO_ACCESS_KEY", "drishtiai")
_MINIO_SECRET   = os.getenv("MINIO_SECRET_KEY", "drishtiai")
_MINIO_SECURE   = os.getenv("MINIO_SECURE", "false").lower() == "true"
_BUCKET         = "exports"
_PRESIGN_DAYS   = 7


def _engine():
    return create_engine(_DB_URL, pool_pre_ping=True)


def _minio() -> Minio:
    return Minio(_MINIO_ENDPOINT, access_key=_MINIO_ACCESS,
                 secret_key=_MINIO_SECRET, secure=_MINIO_SECURE)


def _to_utc(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def _build_pdf(site_id: uuid.UUID, target: date, engine) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

    from_ts = _to_utc(target)
    to_ts   = _to_utc(target + timedelta(days=1))
    params  = {"from_ts": from_ts, "to_ts": to_ts, "sid": site_id}

    with engine.connect() as conn:
        events_total = conn.scalar(text(
            "SELECT COUNT(*) FROM events WHERE ts >= :from_ts AND ts < :to_ts AND site_id = :sid"
        ), params) or 0

        plate_reads = conn.scalar(text(
            "SELECT COUNT(*) FROM events WHERE kind='plate_read' AND ts >= :from_ts AND ts < :to_ts AND site_id = :sid"
        ), params) or 0

        prk = conn.execute(text("""
            SELECT COUNT(*) AS sessions,
                   COALESCE(SUM(amount_due) FILTER (WHERE payment_status='paid'), 0) AS revenue,
                   COALESCE(AVG(duration_s) FILTER (WHERE duration_s IS NOT NULL), 0) AS avg_dur
            FROM parking_sessions WHERE created_at >= :from_ts AND created_at < :to_ts AND site_id = :sid
        """), params).fetchone()

        alert_rows = conn.execute(text("""
            SELECT a.status, COUNT(*) AS cnt FROM alerts a
            JOIN events e ON e.id = a.event_id
            WHERE a.created_at >= :from_ts AND a.created_at < :to_ts AND e.site_id = :sid
            GROUP BY a.status ORDER BY cnt DESC
        """), params).fetchall()

        top_plates = conn.execute(text("""
            SELECT p.text, COUNT(*) AS cnt FROM events e
            JOIN plates p ON p.id = e.plate_id
            WHERE e.kind='plate_read' AND e.ts >= :from_ts AND e.ts < :to_ts AND e.site_id = :sid
            GROUP BY p.text ORDER BY cnt DESC LIMIT 10
        """), params).fetchall()

        hourly = conn.execute(text("""
            SELECT EXTRACT(HOUR FROM ts AT TIME ZONE 'Asia/Kathmandu')::int AS hr, COUNT(*) AS cnt
            FROM events WHERE kind='plate_read' AND ts >= :from_ts AND ts < :to_ts AND site_id = :sid
            GROUP BY hr ORDER BY hr
        """), params).fetchall()

    buf = io.BytesIO()
    styles = getSampleStyleSheet()
    H1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=18, spaceAfter=4)
    H2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=12, spaceBefore=14, spaceAfter=6)
    SIGNAL = colors.HexColor("#3B82F6")
    HAIR   = colors.HexColor("#E2E8F0")

    def tbl(data, widths=None):
        t = Table(data, colWidths=widths)
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),(-1,0), SIGNAL),
            ("TEXTCOLOR",     (0,0),(-1,0), colors.white),
            ("FONTNAME",      (0,0),(-1,0), "Helvetica-Bold"),
            ("FONTSIZE",      (0,0),(-1,-1), 9),
            ("ROWBACKGROUNDS",(0,1),(-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("GRID",          (0,0),(-1,-1), 0.4, HAIR),
            ("LEFTPADDING",   (0,0),(-1,-1), 8),
            ("RIGHTPADDING",  (0,0),(-1,-1), 8),
            ("TOPPADDING",    (0,0),(-1,-1), 5),
            ("BOTTOMPADDING", (0,0),(-1,-1), 5),
        ]))
        return t

    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    content = [
        Paragraph("DrishtiAI — Daily Summary", H1),
        Paragraph(f"Date: {target.strftime('%d %B %Y')}  |  Site: {site_id}  |  Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC",
                  styles["Normal"]),
        Spacer(1, 0.5*cm),

        Paragraph("Traffic", H2),
        tbl([["Metric","Count"],["Total events",str(events_total)],["Plate reads",str(plate_reads)]],
            [10*cm, 5*cm]),
        Spacer(1, 0.3*cm),

        Paragraph("Parking", H2),
        tbl([["Sessions","Revenue (NPR)","Avg duration"],
             [str(prk.sessions if prk else 0),
              f"{(prk.revenue if prk else 0):.2f}",
              f"{int((prk.avg_dur if prk else 0)/60)} min"]],
            [5*cm,5*cm,5*cm]),
        Spacer(1, 0.3*cm),

        Paragraph("Alerts", H2),
        tbl([["Status","Count"]] + [[r.status, str(r.cnt)] for r in alert_rows] or [["Status","Count"],["—","0"]],
            [10*cm, 5*cm]),
        Spacer(1, 0.3*cm),

        Paragraph("Top Plates", H2),
        tbl([["Plate","Reads"]] + [[r.text, str(r.cnt)] for r in top_plates] if top_plates
            else [["Plate","Reads"],["—","0"]],
            [10*cm, 5*cm]),
        Spacer(1, 0.3*cm),

        Paragraph("Hourly Traffic", H2),
        tbl([["Hour","Reads"]] + [[f"{r.hr:02d}:00", str(r.cnt)] for r in hourly] if hourly
            else [["Hour","Reads"],["—","0"]],
            [10*cm, 5*cm]),
    ]
    doc.build(content)
    buf.seek(0)
    return buf.read()


@app.task(name="drishtiai_worker.tasks.reports.generate_daily_report")
def generate_daily_report(site_id: str, date_str: str) -> dict:
    """
    Generate and store a daily summary PDF.
    `date_str` format: YYYY-MM-DD (defaults to yesterday if omitted).
    Returns {"url": presigned_url, "key": minio_key}.
    """
    target = date.fromisoformat(date_str) if date_str else date.today() - timedelta(days=1)
    sid = uuid.UUID(site_id)

    engine = _engine()
    pdf_bytes = _build_pdf(sid, target, engine)

    key = f"reports/{site_id}/{target}/daily_summary.pdf"
    mc = _minio()
    mc.put_object(_BUCKET, key, io.BytesIO(pdf_bytes), len(pdf_bytes),
                  content_type="application/pdf")
    url = mc.presigned_get_object(_BUCKET, key, expires=timedelta(days=_PRESIGN_DAYS))
    return {"url": url, "key": key, "bytes": len(pdf_bytes)}


@app.task(name="drishtiai_worker.tasks.reports.generate_monthly_report")
def generate_monthly_report(site_id: str, month: str) -> dict:
    """
    Generate a month-range PDF (same format, wider date window).
    `month` format: YYYY-MM
    """
    year, mon = int(month[:4]), int(month[5:7])
    from_date = date(year, mon, 1)
    # Last day of month
    if mon == 12:
        to_date = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        to_date = date(year, mon + 1, 1) - timedelta(days=1)

    sid = uuid.UUID(site_id)
    engine = _engine()

    # Re-use the daily builder with from/to spanning the full month
    # by temporarily setting target to from_date and patching params inside _build_pdf
    # Simplest approach: call it day-by-day and concatenate, or just run the wider window.
    # For now: use the from/to dates directly (wider query window than daily).
    from_ts = _to_utc(from_date)
    to_ts   = _to_utc(to_date + timedelta(days=1))

    # Build using the same PDF structure but with monthly params
    pdf_bytes = _build_pdf_range(sid, from_date, to_date, engine)

    key = f"reports/{site_id}/{month}/monthly_summary.pdf"
    mc = _minio()
    mc.put_object(_BUCKET, key, io.BytesIO(pdf_bytes), len(pdf_bytes),
                  content_type="application/pdf")
    url = mc.presigned_get_object(_BUCKET, key, expires=timedelta(days=_PRESIGN_DAYS))
    return {"url": url, "key": key, "bytes": len(pdf_bytes)}


def _build_pdf_range(site_id: uuid.UUID, from_date: date, to_date: date, engine) -> bytes:
    """Same as _build_pdf but for an arbitrary date range."""
    # Patch _build_pdf to use from_date as `target` but override to/from_ts
    # The simplest reuse: create a synthetic single-day PDF labelled with the range
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

    from_ts = _to_utc(from_date)
    to_ts   = _to_utc(to_date + timedelta(days=1))
    params  = {"from_ts": from_ts, "to_ts": to_ts, "sid": site_id}

    with engine.connect() as conn:
        events_total = conn.scalar(text(
            "SELECT COUNT(*) FROM events WHERE ts >= :from_ts AND ts < :to_ts AND site_id = :sid"
        ), params) or 0
        plate_reads = conn.scalar(text(
            "SELECT COUNT(*) FROM events WHERE kind='plate_read' AND ts >= :from_ts AND ts < :to_ts AND site_id = :sid"
        ), params) or 0
        prk = conn.execute(text("""
            SELECT COUNT(*) AS sessions,
                   COALESCE(SUM(amount_due) FILTER (WHERE payment_status='paid'), 0) AS revenue
            FROM parking_sessions WHERE created_at >= :from_ts AND created_at < :to_ts AND site_id = :sid
        """), params).fetchone()
        top_plates = conn.execute(text("""
            SELECT p.text, COUNT(*) AS cnt FROM events e
            JOIN plates p ON p.id = e.plate_id
            WHERE e.kind='plate_read' AND e.ts >= :from_ts AND e.ts < :to_ts AND e.site_id = :sid
            GROUP BY p.text ORDER BY cnt DESC LIMIT 20
        """), params).fetchall()

    buf = io.BytesIO()
    styles = getSampleStyleSheet()
    H1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=18, spaceAfter=4)
    H2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=12, spaceBefore=14, spaceAfter=6)
    SIGNAL = colors.HexColor("#3B82F6")
    HAIR   = colors.HexColor("#E2E8F0")

    def tbl(data, widths=None):
        t = Table(data, colWidths=widths)
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),(-1,0), SIGNAL),
            ("TEXTCOLOR",     (0,0),(-1,0), colors.white),
            ("FONTNAME",      (0,0),(-1,0), "Helvetica-Bold"),
            ("FONTSIZE",      (0,0),(-1,-1), 9),
            ("ROWBACKGROUNDS",(0,1),(-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("GRID",          (0,0),(-1,-1), 0.4, HAIR),
            ("LEFTPADDING",   (0,0),(-1,-1), 8),
            ("RIGHTPADDING",  (0,0),(-1,-1), 8),
            ("TOPPADDING",    (0,0),(-1,-1), 5),
            ("BOTTOMPADDING", (0,0),(-1,-1), 5),
        ]))
        return t

    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    content = [
        Paragraph("DrishtiAI — Monthly Summary", H1),
        Paragraph(f"Period: {from_date} → {to_date}  |  Site: {site_id}",
                  styles["Normal"]),
        Spacer(1, 0.5*cm),
        Paragraph("Traffic", H2),
        tbl([["Metric","Count"],["Total events",str(events_total)],["Plate reads",str(plate_reads)]],
            [10*cm,5*cm]),
        Spacer(1,0.3*cm),
        Paragraph("Parking", H2),
        tbl([["Sessions","Revenue (NPR)"],
             [str(prk.sessions if prk else 0), f"{(prk.revenue if prk else 0):.2f}"]],
            [7*cm,8*cm]),
        Spacer(1,0.3*cm),
        Paragraph("Top 20 Plates", H2),
        tbl([["Plate","Reads"]] + [[r.text, str(r.cnt)] for r in top_plates] if top_plates
            else [["Plate","Reads"],["—","0"]],
            [10*cm,5*cm]),
    ]
    doc.build(content)
    buf.seek(0)
    return buf.read()
