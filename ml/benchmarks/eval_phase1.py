"""
Phase 1 acceptance benchmark evaluator.

Reads phase1_gt.json (written by generate_test_video.py), queries Postgres for
events that were captured during the test run, and reports recall + latency.

Usage (run after pipeline processes the test video):

    uv run python ml/benchmarks/eval_phase1.py \
        --gt ml/benchmarks/phase1_gt.json \
        --db postgresql://drishtiai:drishtiai@localhost:5432/drishtiai \
        --window 3600          # look-back window in seconds (default 1 hour)

Exit codes:
    0  all acceptance criteria met
    1  one or more criteria failed
    2  usage / connection error
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import psycopg


@dataclass
class PlateMatch:
    expected: str
    detected: str | None = None
    latency_s: float | None = None


def query_detected_plates(
    db_url: str,
    since: datetime,
) -> list[dict[str, Any]]:
    """Return all plate_read events created since `since`."""
    sql = """
        SELECT e.ts, p.text AS plate_text
        FROM events e
        JOIN plates p ON p.id = e.plate_id
        WHERE e.kind = 'plate_read'
          AND e.ts >= %(since)s
        ORDER BY e.ts ASC
    """
    rows = []
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"since": since})
            for row in cur.fetchall():
                rows.append({"ts": row[0], "plate_text": row[1]})
    return rows


def normalise(text: str) -> str:
    return text.upper().replace(" ", "").replace("-", "")


def evaluate(
    expected_plates: list[dict[str, Any]],
    detected_rows: list[dict[str, Any]],
    video_start: datetime,
    min_recall: float,
    max_latency_s: float,
) -> tuple[bool, dict[str, Any]]:
    detected_norm = [
        {"ts": r["ts"], "text": normalise(r["plate_text"])}
        for r in detected_rows
    ]

    matches: list[PlateMatch] = []
    for spec in expected_plates:
        expected_text = normalise(spec["text"])
        plate_appears_at = video_start + timedelta(seconds=spec["appears_at_s"])
        plate_vanishes_at = video_start + timedelta(seconds=spec["disappears_at_s"])
        deadline = plate_appears_at + timedelta(seconds=max_latency_s)

        m = PlateMatch(expected=spec["text"])
        for det in detected_norm:
            if det["text"] == expected_text and det["ts"] >= plate_appears_at:
                m.detected = det["text"]
                m.latency_s = (det["ts"] - plate_appears_at).total_seconds()
                break
        matches.append(m)

    detected_count  = sum(1 for m in matches if m.detected is not None)
    on_time_count   = sum(1 for m in matches
                          if m.detected and m.latency_s is not None
                          and m.latency_s <= max_latency_s)
    total = len(matches)
    recall          = detected_count / total if total else 0.0
    on_time_recall  = on_time_count  / total if total else 0.0

    passed = recall >= min_recall and on_time_recall >= min_recall

    report: dict[str, Any] = {
        "passed": passed,
        "recall": round(recall, 4),
        "on_time_recall": round(on_time_recall, 4),
        "detected": detected_count,
        "total": total,
        "criteria": {
            "min_recall": min_recall,
            "max_latency_s": max_latency_s,
        },
        "details": [
            {
                "plate": m.expected,
                "detected": m.detected is not None,
                "latency_s": round(m.latency_s, 2) if m.latency_s is not None else None,
                "on_time": (
                    m.latency_s is not None and m.latency_s <= max_latency_s
                    if m.latency_s is not None else False
                ),
            }
            for m in matches
        ],
    }
    return passed, report


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 1 benchmark evaluator")
    parser.add_argument("--gt",     default="ml/benchmarks/phase1_gt.json")
    parser.add_argument("--db",     default="postgresql://drishtiai:drishtiai@localhost:5432/drishtiai")
    parser.add_argument("--window", type=int, default=3600,
                        help="Look-back window in seconds for detected events (default 3600)")
    parser.add_argument("--video-start",
                        help="ISO timestamp when the test video started streaming. "
                             "Defaults to (now - window).")
    args = parser.parse_args()

    gt_path = Path(args.gt)
    if not gt_path.exists():
        print(f"ERROR: ground truth file not found: {gt_path}", file=sys.stderr)
        return 2

    gt = json.loads(gt_path.read_text())
    expected_plates   = gt["expected_plates"]
    min_recall        = gt["acceptance_criteria"]["min_recall"]
    max_latency_s     = gt["acceptance_criteria"]["max_latency_s"]

    now = datetime.now(tz=timezone.utc)
    if args.video_start:
        video_start = datetime.fromisoformat(args.video_start)
        if video_start.tzinfo is None:
            video_start = video_start.replace(tzinfo=timezone.utc)
    else:
        video_start = now - timedelta(seconds=args.window)

    since = video_start

    print(f"Querying DB for events since {since.isoformat()} …")
    try:
        detected_rows = query_detected_plates(args.db, since)
    except Exception as exc:
        print(f"ERROR: DB connection failed: {exc}", file=sys.stderr)
        return 2

    print(f"Found {len(detected_rows)} plate_read events.")
    passed, report = evaluate(
        expected_plates=expected_plates,
        detected_rows=detected_rows,
        video_start=video_start,
        min_recall=min_recall,
        max_latency_s=max_latency_s,
    )

    print(json.dumps(report, indent=2))

    print()
    if passed:
        print(f"PASS  recall={report['recall']:.0%}  on_time_recall={report['on_time_recall']:.0%}")
    else:
        print(f"FAIL  recall={report['recall']:.0%}  on_time_recall={report['on_time_recall']:.0%}  "
              f"(need >= {min_recall:.0%})")

    # Print miss list for easy debugging
    missed = [d for d in report["details"] if not d["detected"]]
    if missed:
        print(f"\nMissed plates ({len(missed)}):")
        for m in missed:
            print(f"  {m['plate']}")

    late = [d for d in report["details"] if d["detected"] and not d["on_time"]]
    if late:
        print(f"\nLate detections ({len(late)}):")
        for m in late:
            print(f"  {m['plate']}  latency={m['latency_s']}s (limit={max_latency_s}s)")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
