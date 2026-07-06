"""
Head-to-head comparison: DrishtiAI OCR vs. Plate Recognizer API.

This script evaluates both systems on the same labelled image set and produces
a side-by-side accuracy report. Useful for gating model upgrades and for
demonstrating improvement over a third-party baseline.

Usage:
    # Run both systems
    uv run python ml/benchmarks/compare_plate_recognizer.py \
        --image-dir ml/benchmarks/nepali_plates_test/ \
        --gt        ml/benchmarks/nepali_gt.json \
        --pr-token  $PLATE_RECOGNIZER_TOKEN

    # Skip Plate Recognizer (no token / offline)
    uv run python ml/benchmarks/compare_plate_recognizer.py \
        --image-dir ml/benchmarks/nepali_plates_test/ \
        --gt        ml/benchmarks/nepali_gt.json \
        --no-pr

Outputs:
    ml/benchmarks/results/comparison-<timestamp>.json — full per-image table
    Console — aligned summary table with pass/fail against targets

Plate Recognizer API: https://platerecognizer.com
  Requires a free or paid API token (PLATE_RECOGNIZER_TOKEN env var or --pr-token).
  Free tier: 2500 lookups/month.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time
from datetime import datetime, timezone


# ── CER helper (copied from eval_nepali_ocr to keep this script standalone) ─

def _cer(gt: str, pred: str) -> float:
    if not gt:
        return 0.0 if not pred else 1.0
    n, m = len(gt), len(pred)
    prev = list(range(n + 1))
    for j in range(1, m + 1):
        curr = [j] + [0] * n
        for i in range(1, n + 1):
            if gt[i - 1] == pred[j - 1]:
                curr[i] = prev[i - 1]
            else:
                curr[i] = 1 + min(prev[i], curr[i - 1], prev[i - 1])
        prev = curr
    return min(prev[n] / n, 1.0)


def _normalize(text: str) -> str:
    return text.upper().replace(" ", "").replace("-", "").strip()


# ── DrishtiAI prediction ──────────────────────────────────────────────────────

def _drishtiai_predict(image_path: pathlib.Path) -> str:
    try:
        import cv2
        from drishtiai_pipeline.ocr import detect_plates
    except ImportError:
        return "__PIPELINE_NOT_INSTALLED__"

    frame = cv2.imread(str(image_path))
    if frame is None:
        return ""
    detections = detect_plates(frame)
    if not detections:
        return ""
    best = max(detections, key=lambda d: d.confidence)
    return _normalize(best.text)


# ── Plate Recognizer prediction ───────────────────────────────────────────────

def _pr_predict(image_path: pathlib.Path, token: str, session) -> str:
    """Call Plate Recognizer cloud API.  Returns normalised plate text or "".
    Raises RuntimeError on non-200 that is not a quota exceeded."""
    try:
        import requests  # type: ignore[import]
    except ImportError:
        raise SystemExit("requests not installed — run: uv add requests")

    with image_path.open("rb") as f:
        resp = session.post(
            "https://api.platerecognizer.com/v1/plate-reader/",
            headers={"Authorization": f"Token {token}"},
            files={"upload": f},
            data={"regions": ["np"]},
            timeout=15,
        )

    if resp.status_code == 429:
        print("  [PR] Rate limited — sleeping 60s", file=sys.stderr)
        time.sleep(60)
        return _pr_predict(image_path, token, session)

    if resp.status_code != 201:
        raise RuntimeError(f"Plate Recognizer API error {resp.status_code}: {resp.text[:200]}")

    results = resp.json().get("results", [])
    if not results:
        return ""
    return _normalize(results[0].get("plate", ""))


# ── Metrics helper ────────────────────────────────────────────────────────────

def _metrics(gt_list: list[str], pred_list: list[str]) -> dict:
    exact = sum(g == p for g, p in zip(gt_list, pred_list))
    total = len(gt_list)
    cer_sum = sum(_cer(g, p) for g, p in zip(gt_list, pred_list))
    prov_match = sum(
        len(g) >= 2 and len(p) >= 2 and g[:2] == p[:2]
        for g, p in zip(gt_list, pred_list)
    )
    return {
        "plate_accuracy": round(exact / total, 4) if total else 0.0,
        "province_accuracy": round(prov_match / total, 4) if total else 0.0,
        "mean_cer": round(cer_sum / total, 4) if total else 0.0,
        "total": total,
        "exact_matches": exact,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Compare DrishtiAI OCR vs. Plate Recognizer")
    parser.add_argument("--image-dir", required=True, type=pathlib.Path)
    parser.add_argument("--gt",        required=True, type=pathlib.Path)
    parser.add_argument("--pr-token",  default=os.environ.get("PLATE_RECOGNIZER_TOKEN", ""))
    parser.add_argument("--no-pr",     action="store_true", help="Skip Plate Recognizer API calls")
    parser.add_argument("--out-dir",   default="ml/benchmarks/results", type=pathlib.Path)
    parser.add_argument("--limit",     type=int, default=0, help="Max images to evaluate (0 = all)")
    args = parser.parse_args()

    if not args.no_pr and not args.pr_token:
        print(
            "WARNING: No Plate Recognizer token — use --pr-token or PLATE_RECOGNIZER_TOKEN env var.\n"
            "         Running with --no-pr (DrishtiAI only).",
            file=sys.stderr,
        )
        args.no_pr = True

    gt: dict[str, dict] = json.loads(args.gt.read_text(encoding="utf-8"))
    filenames = list(gt.keys())
    if args.limit > 0:
        filenames = filenames[:args.limit]

    rows: list[dict] = []
    drishti_gts: list[str] = []
    drishti_preds: list[str] = []
    pr_gts: list[str] = []
    pr_preds: list[str] = []

    session = None
    if not args.no_pr:
        try:
            import requests  # type: ignore[import]
            session = requests.Session()
        except ImportError:
            raise SystemExit("requests not installed — run: uv add requests")

    print(f"Evaluating {len(filenames)} images…")
    for i, filename in enumerate(filenames, 1):
        meta = gt[filename]
        gt_text = _normalize(meta["plate_text"])
        image_path = args.image_dir / filename

        if not image_path.exists():
            print(f"  SKIP {filename} — not found", file=sys.stderr)
            continue

        drishti_pred = _drishtiai_predict(image_path)
        pr_pred = "" if args.no_pr else _pr_predict(image_path, args.pr_token, session)

        row = {
            "filename": filename,
            "plate_type": meta.get("plate_type", "embossed"),
            "condition": meta.get("condition", "unknown"),
            "gt": gt_text,
            "drishti_pred": drishti_pred,
            "drishti_exact": drishti_pred == gt_text,
            "drishti_cer": round(_cer(gt_text, drishti_pred), 4),
        }
        drishti_gts.append(gt_text)
        drishti_preds.append(drishti_pred)

        if not args.no_pr:
            row["pr_pred"] = pr_pred
            row["pr_exact"] = pr_pred == gt_text
            row["pr_cer"] = round(_cer(gt_text, pr_pred), 4)
            pr_gts.append(gt_text)
            pr_preds.append(pr_pred)

        rows.append(row)

        if i % 50 == 0:
            print(f"  {i}/{len(filenames)}")

    drishti_m = _metrics(drishti_gts, drishti_preds)
    report = {
        "evaluated_at": datetime.now(tz=timezone.utc).isoformat(),
        "total_evaluated": len(rows),
        "drishtiai": drishti_m,
        "rows": rows,
    }
    if not args.no_pr:
        pr_m = _metrics(pr_gts, pr_preds)
        report["plate_recognizer"] = pr_m

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%S")
    out_path = args.out_dir / f"comparison-{stamp}.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    # ── Print summary ──────────────────────────────────────────────────────
    w = 40
    print(f"\n{'─' * w}")
    print(f"{'Metric':<24} {'DrishtiAI':>8}", end="")
    if not args.no_pr:
        print(f"  {'PlateRecog':>10}", end="")
    print()
    print(f"{'─' * w}")

    rows_data = [
        ("Plate accuracy", "plate_accuracy", "≥92%"),
        ("Province accuracy", "province_accuracy", ""),
        ("Mean CER", "mean_cer", "≤8%"),
    ]
    for label, key, target in rows_data:
        d_val = drishti_m[key]
        d_str = f"{d_val * 100:.1f}%"
        line = f"  {label:<22} {d_str:>8}"
        if not args.no_pr:
            pr_val = report["plate_recognizer"][key]  # type: ignore[index]
            pr_str = f"{pr_val * 100:.1f}%"
            line += f"  {pr_str:>10}"
        if target:
            line += f"  (target {target})"
        print(line)

    print(f"{'─' * w}")
    print(f"\nFull results: {out_path}")


if __name__ == "__main__":
    main()
