"""
Report export endpoints — Phase 8.

CSV exports use Python stdlib csv; no new runtime deps.
PDF uses reportlab (BSD licensed).
All queries are time-bounded to hit the events partition index.
"""
import csv
import io
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import text

from drishtiai_api.deps import CurrentUser, DbSession

router = APIRouter()

# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_utc(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def _csv_response(rows: list[list], headers: list[str], filename: str) -> StreamingResponse:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    writer.writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _default_range() -> tuple[date, date]:
    today = date.today()
    return today - timedelta(days=7), today


# ── Events CSV ────────────────────────────────────────────────────────────────

@router.get("/events.csv")
async def events_csv(
    current_user: CurrentUser,
    db: DbSession,
    site_id: Annotated[uuid.UUID | None, Query()] = None,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
):
    df, dt = from_date or _default_range()[0], to_date or _default_range()[1]
    from_ts = _to_utc(df)
    to_ts = _to_utc(dt + timedelta(days=1))

    sid = site_id or (uuid.UUID(current_user.site_ids[0]) if current_user.site_ids else None)

    rows = db.execute(
        text("""
            SELECT
                e.ts AT TIME ZONE 'UTC' AS ts,
                e.kind,
                p.text AS plate,
                c.name AS camera,
                e.confidence,
                e.id
            FROM events e
            LEFT JOIN plates p ON p.id = e.plate_id
            LEFT JOIN cameras c ON c.id = e.camera_id
            WHERE e.ts >= :from_ts
              AND e.ts < :to_ts
              AND (:sid IS NULL OR e.site_id = :sid)
            ORDER BY e.ts DESC
            LIMIT 50000
        """),
        {"from_ts": from_ts, "to_ts": to_ts, "sid": sid},
    ).fetchall()

    data = [
        [str(r.ts), r.kind, r.plate or "", r.camera or "", r.confidence or "", str(r.id)]
        for r in rows
    ]
    filename = f"events_{df}_{dt}.csv"
    return _csv_response(data, ["timestamp", "kind", "plate", "camera", "confidence", "event_id"], filename)


# ── Parking CSV ───────────────────────────────────────────────────────────────

@router.get("/parking.csv")
async def parking_csv(
    current_user: CurrentUser,
    db: DbSession,
    site_id: Annotated[uuid.UUID | None, Query()] = None,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
):
    df, dt = from_date or _default_range()[0], to_date or _default_range()[1]
    from_ts = _to_utc(df)
    to_ts = _to_utc(dt + timedelta(days=1))

    sid = site_id or (uuid.UUID(current_user.site_ids[0]) if current_user.site_ids else None)

    rows = db.execute(
        text("""
            SELECT
                ps.created_at AT TIME ZONE 'UTC' AS entry_time,
                ps.updated_at AT TIME ZONE 'UTC' AS exit_time,
                p.text AS plate,
                ps.duration_s,
                ps.amount_due,
                ps.payment_status,
                ps.id
            FROM parking_sessions ps
            LEFT JOIN plates p ON p.id = ps.plate_id
            WHERE ps.created_at >= :from_ts
              AND ps.created_at < :to_ts
              AND (:sid IS NULL OR ps.site_id = :sid)
            ORDER BY ps.created_at DESC
            LIMIT 20000
        """),
        {"from_ts": from_ts, "to_ts": to_ts, "sid": sid},
    ).fetchall()

    currency = "NPR"
    data = [
        [
            str(r.entry_time),
            str(r.exit_time) if r.exit_time else "",
            r.plate or "",
            r.duration_s or "",
            f"{r.amount_due:.2f}" if r.amount_due is not None else "",
            r.payment_status,
            str(r.id),
        ]
        for r in rows
    ]
    filename = f"parking_{df}_{dt}.csv"
    headers = ["entry_time", "exit_time", "plate", "duration_s", f"amount_{currency}", "payment_status", "session_id"]
    return _csv_response(data, headers, filename)


# ── Alerts CSV ────────────────────────────────────────────────────────────────

@router.get("/alerts.csv")
async def alerts_csv(
    current_user: CurrentUser,
    db: DbSession,
    site_id: Annotated[uuid.UUID | None, Query()] = None,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
):
    df, dt = from_date or _default_range()[0], to_date or _default_range()[1]
    from_ts = _to_utc(df)
    to_ts = _to_utc(dt + timedelta(days=1))

    sid = site_id or (uuid.UUID(current_user.site_ids[0]) if current_user.site_ids else None)

    rows = db.execute(
        text("""
            SELECT
                a.created_at AT TIME ZONE 'UTC' AS ts,
                p.text AS plate,
                wl.name AS watchlist,
                wl.category,
                a.status,
                a.ack_at AT TIME ZONE 'UTC' AS ack_at,
                a.notes,
                a.id
            FROM alerts a
            JOIN events e ON e.id = a.event_id
            LEFT JOIN plates p ON p.id = e.plate_id
            LEFT JOIN watchlists wl ON wl.id = a.watchlist_id
            WHERE a.created_at >= :from_ts
              AND a.created_at < :to_ts
              AND (:sid IS NULL OR e.site_id = :sid)
            ORDER BY a.created_at DESC
            LIMIT 20000
        """),
        {"from_ts": from_ts, "to_ts": to_ts, "sid": sid},
    ).fetchall()

    data = [
        [str(r.ts), r.plate or "", r.watchlist or "", r.category or "", r.status,
         str(r.ack_at) if r.ack_at else "", r.notes or "", str(r.id)]
        for r in rows
    ]
    filename = f"alerts_{df}_{dt}.csv"
    return _csv_response(data, ["timestamp", "plate", "watchlist", "category", "status", "ack_at", "notes", "alert_id"], filename)


# ── Daily Summary PDF ─────────────────────────────────────────────────────────

@router.get("/daily-summary.pdf")
async def daily_summary_pdf(
    current_user: CurrentUser,
    db: DbSession,
    site_id: Annotated[uuid.UUID | None, Query()] = None,
    report_date: Annotated[date | None, Query(alias="date")] = None,
):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

    target = report_date or (date.today() - timedelta(days=1))
    from_ts = _to_utc(target)
    to_ts = _to_utc(target + timedelta(days=1))

    sid = site_id or (uuid.UUID(current_user.site_ids[0]) if current_user.site_ids else None)
    params = {"from_ts": from_ts, "to_ts": to_ts, "sid": sid}

    # ── Queries ────────────────────────────────────────────────────────────────
    events_total = db.scalar(text(
        "SELECT COUNT(*) FROM events WHERE ts >= :from_ts AND ts < :to_ts "
        "AND (:sid IS NULL OR site_id = :sid)"
    ), params) or 0

    plate_reads = db.scalar(text(
        "SELECT COUNT(*) FROM events WHERE kind = 'plate_read' AND ts >= :from_ts AND ts < :to_ts "
        "AND (:sid IS NULL OR site_id = :sid)"
    ), params) or 0

    parking_rows = db.execute(text("""
        SELECT
            COUNT(*) AS sessions,
            COALESCE(SUM(amount_due) FILTER (WHERE payment_status = 'paid'), 0) AS revenue,
            COALESCE(AVG(duration_s) FILTER (WHERE duration_s IS NOT NULL), 0) AS avg_dur
        FROM parking_sessions
        WHERE created_at >= :from_ts AND created_at < :to_ts
          AND (:sid IS NULL OR site_id = :sid)
    """), params).fetchone()

    alert_rows = db.execute(text("""
        SELECT a.status, COUNT(*) AS cnt
        FROM alerts a
        JOIN events e ON e.id = a.event_id
        WHERE a.created_at >= :from_ts AND a.created_at < :to_ts
          AND (:sid IS NULL OR e.site_id = :sid)
        GROUP BY a.status
        ORDER BY cnt DESC
    """), params).fetchall()

    top_plates = db.execute(text("""
        SELECT p.text, COUNT(*) AS cnt
        FROM events e
        JOIN plates p ON p.id = e.plate_id
        WHERE e.kind = 'plate_read' AND e.ts >= :from_ts AND e.ts < :to_ts
          AND (:sid IS NULL OR e.site_id = :sid)
        GROUP BY p.text
        ORDER BY cnt DESC
        LIMIT 10
    """), params).fetchall()

    hourly = db.execute(text("""
        SELECT EXTRACT(HOUR FROM ts AT TIME ZONE 'Asia/Kathmandu')::int AS hr, COUNT(*) AS cnt
        FROM events
        WHERE kind = 'plate_read' AND ts >= :from_ts AND ts < :to_ts
          AND (:sid IS NULL OR site_id = :sid)
        GROUP BY hr ORDER BY hr
    """), params).fetchall()

    # ── Build PDF ──────────────────────────────────────────────────────────────
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    styles = getSampleStyleSheet()
    H1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=18, spaceAfter=4)
    H2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=12, spaceBefore=14, spaceAfter=6)
    NORMAL = styles["Normal"]

    INK  = colors.HexColor("#0B0F14")
    SIGNAL = colors.HexColor("#3B82F6")
    HAIR = colors.HexColor("#E2E8F0")

    def tbl(data, col_widths=None):
        t = Table(data, colWidths=col_widths)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), SIGNAL),
            ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
            ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",   (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("GRID",       (0, 0), (-1, -1), 0.4, HAIR),
            ("LEFTPADDING",  (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING",   (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
        ]))
        return t

    content = [
        Paragraph("DrishtiAI — Daily Summary", H1),
        Paragraph(f"Date: {target.strftime('%d %B %Y')}  |  Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC", NORMAL),
        Spacer(1, 0.5*cm),

        Paragraph("Traffic Overview", H2),
        tbl(
            [["Metric", "Count"],
             ["Total events", str(events_total)],
             ["Plate reads", str(plate_reads)]],
            col_widths=[10*cm, 5*cm],
        ),
        Spacer(1, 0.3*cm),

        Paragraph("Parking", H2),
        tbl(
            [["Sessions", "Revenue (NPR)", "Avg duration"],
             [str(parking_rows.sessions if parking_rows else 0),
              f"{(parking_rows.revenue if parking_rows else 0):.2f}",
              f"{int((parking_rows.avg_dur if parking_rows else 0) / 60)} min"]],
            col_widths=[5*cm, 5*cm, 5*cm],
        ),
        Spacer(1, 0.3*cm),

        Paragraph("Alerts by Status", H2),
        tbl(
            [["Status", "Count"]] + [[r.status, str(r.cnt)] for r in alert_rows] or [["Status", "Count"], ["—", "0"]],
            col_widths=[10*cm, 5*cm],
        ),
        Spacer(1, 0.3*cm),

        Paragraph("Top Plates", H2),
        tbl(
            [["Plate", "Reads"]] + [[r.text, str(r.cnt)] for r in top_plates] if top_plates
            else [["Plate", "Reads"], ["—", "0"]],
            col_widths=[10*cm, 5*cm],
        ),
        Spacer(1, 0.3*cm),

        Paragraph("Hourly Traffic (plate reads)", H2),
        tbl(
            [["Hour", "Reads"]] + [[f"{r.hr:02d}:00", str(r.cnt)] for r in hourly] if hourly
            else [["Hour", "Reads"], ["—", "0"]],
            col_widths=[10*cm, 5*cm],
        ),
    ]

    doc.build(content)
    buf.seek(0)
    filename = f"daily_summary_{target}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
