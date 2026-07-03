"""
Phase 11 OCR benchmark — character accuracy + precision + recall.

Extends the Phase 1 evaluator with:
  • Character Error Rate (CER) — Levenshtein distance / expected length
  • Precision — what fraction of detected plates are correct
  • False positive list — plates detected that are not in ground truth

Usage:

    uv run python ml/benchmarks/eval_phase11.py \\
        --gt ml/benchmarks/phase1_gt.json \\
        --db postgresql://drishtiai:drishtiai@localhost:5432/drishtiai \\
        --window 3600

Exit codes:
    0  all acceptance criteria met
    1  one or more criteria failed
    2  usage / connection error
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _levenshtein(a: str, b: str) -> int:
    """Compute edit distance between two strings."""
    if a == b:
        return 0
    m, n = len(a), len(b)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            temp = dp[j]
            if a[i - 1] == b[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j - 1])
            prev = temp
    return dp[n]


def normalise(text: str) -> str:
    return text.upper().replace(" ", "").replace("-", "")


def query_detected(db_url: str, since: datetime) -> list[dict[str, Any]]:
    import psycopg
    sql = """
        SELECT e.ts, p.text AS plate_text
        FROM events e
        JOIN plates p ON p.id = e.plate_id
        WHERE e.kind = 'plate_read' AND e.ts >= %(since)s
        ORDER BY e.ts ASC
    """
    rows: list[dict[str, Any]] = []
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"since": since})
            for row in cur.fetchall():
                rows.append({"ts": row[0], "plate_text": row[1]})
    return rows


def evaluate(
    expected: list[dict[str, Any]],
    detected: list[dict[str, Any]],
    video_start: datetime,
    min_recall: float,
    max_latency_s: float,
    min_precision: float = 0.70,
    max_cer: float = 0.10,
) -> tuple[bool, dict[str, Any]]:
    detected_norm = [
        {"ts": r["ts"], "text": normalise(r["plate_text"])}
        for r in detected
    ]
    expected_set = {normalise(e["text"]) for e in expected}

    # ── Per-plate matching ────────────────────────────────────────────────────
    details = []
    total_cer = 0.0
    detected_count = 0
    on_time_count = 0

    for spec in expected:
        exp_text = normalise(spec["text"])
        appears_at = video_start + timedelta(seconds=spec["appears_at_s"])
        deadline = appears_at + timedelta(seconds=max_latency_s)

        best_match: dict[str, Any] | None = None
        best_dist = len(exp_text)  # worst case: replace all chars

        for det in detected_norm:
            if det["ts"] < appears_at:
                continue
            dist = _levenshtein(det["text"], exp_text)
            # Accept as a match if ≤1 char error (covers single OCR substitution)
            if dist <= 1 and dist < best_dist:
                best_dist = dist
                best_match = det

        cer = best_dist / max(len(exp_text), 1) if best_match is None else best_dist / len(exp_text)
        total_cer += cer

        matched = best_match is not None
        latency = (best_match["ts"] - appears_at).total_seconds() if matched else None
        on_time = matched and latency is not None and latency <= max_latency_s

        if matched:
            detected_count += 1
        if on_time:
            on_time_count += 1

        details.append({
            "plate": spec["text"],
            "detected": matched,
            "latency_s": round(latency, 2) if latency is not None else None,
            "on_time": on_time,
            "cer": round(cer, 4),
            "matched_as": best_match["text"] if best_match else None,
        })

    total = len(expected)
    recall = detected_count / total if total else 0.0
    on_time_recall = on_time_count / total if total else 0.0
    avg_cer = total_cer / total if total else 0.0

    # ── Precision (false positive rate) ──────────────────────────────────────
    false_positives = [
        d["text"] for d in detected_norm
        if d["text"] not in expected_set
        and not any(_levenshtein(d["text"], e) <= 1 for e in expected_set)
    ]
    # Deduplicate FPs
    fp_unique = sorted(set(false_positives))
    total_det = len(detected_norm)
    precision = (total_det - len(false_positives)) / total_det if total_det else 1.0

    passed = (
        recall >= min_recall
        and on_time_recall >= min_recall
        and precision >= min_precision
        and avg_cer <= max_cer
    )

    report: dict[str, Any] = {
        "passed": passed,
        "recall": round(recall, 4),
        "on_time_recall": round(on_time_recall, 4),
        "precision": round(precision, 4),
        "avg_cer": round(avg_cer, 4),
        "detected": detected_count,
        "total": total,
        "false_positives": fp_unique,
        "criteria": {
            "min_recall": min_recall,
            "max_latency_s": max_latency_s,
            "min_precision": min_precision,
            "max_cer": max_cer,
        },
        "details": details,
    }
    return passed, report


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 11 OCR benchmark evaluator")
    parser.add_argument("--gt",           default="ml/benchmarks/phase1_gt.json")
    parser.add_argument("--db",           default="postgresql://drishtiai:drishtiai@localhost:5432/drishtiai")
    parser.add_argument("--window",       type=int, default=3600)
    parser.add_argument("--video-start",  help="ISO timestamp when the test video started")
    parser.add_argument("--min-recall",   type=float, default=None)
    parser.add_argument("--min-precision",type=float, default=0.70)
    parser.add_argument("--max-cer",      type=float, default=0.10)
    args = parser.parse_args()

    gt_path = Path(args.gt)
    if not gt_path.exists():
        print(f"ERROR: ground truth file not found: {gt_path}", file=sys.stderr)
        return 2

    gt = json.loads(gt_path.read_text())
    expected_plates = gt["expected_plates"]
    min_recall = args.min_recall or gt["acceptance_criteria"]["min_recall"]
    max_latency_s = gt["acceptance_criteria"]["max_latency_s"]

    now = datetime.now(tz=timezone.utc)
    video_start = (
        datetime.fromisoformat(args.video_start).replace(tzinfo=timezone.utc)
        if args.video_start
        else now - timedelta(seconds=args.window)
    )

    print(f"Querying DB for events since {video_start.isoformat()} …")
    try:
        detected_rows = query_detected(args.db, video_start)
    except Exception as exc:
        print(f"ERROR: DB connection failed: {exc}", file=sys.stderr)
        return 2

    print(f"Found {len(detected_rows)} plate_read events.")
    passed, report = evaluate(
        expected=expected_plates,
        detected=detected_rows,
        video_start=video_start,
        min_recall=min_recall,
        max_latency_s=max_latency_s,
        min_precision=args.min_precision,
        max_cer=args.max_cer,
    )

    print(json.dumps(report, indent=2))
    print()

    status = "PASS" if passed else "FAIL"
    print(
        f"{status}  recall={report['recall']:.0%}  "
        f"on_time={report['on_time_recall']:.0%}  "
        f"precision={report['precision']:.0%}  "
        f"avg_cer={report['avg_cer']:.2%}"
    )

    missed = [d for d in report["details"] if not d["detected"]]
    if missed:
        print(f"\nMissed ({len(missed)}):")
        for m in missed:
            print(f"  {m['plate']}")

    if report["false_positives"]:
        print(f"\nFalse positives ({len(report['false_positives'])}):")
        for fp in report["false_positives"]:
            print(f"  {fp}")

    late = [d for d in report["details"] if d["detected"] and not d["on_time"]]
    if late:
        print(f"\nLate ({len(late)}):")
        for m in late:
            print(f"  {m['plate']}  {m['latency_s']}s  (matched as {m['matched_as']})")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
