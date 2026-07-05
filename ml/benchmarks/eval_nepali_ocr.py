"""
Evaluate OCR accuracy on a labelled Nepali plate image dataset.

Usage:
    python ml/benchmarks/eval_nepali_ocr.py \
        --image-dir ml/benchmarks/nepali_plates_test/ \
        --gt ml/benchmarks/phase1_gt.json

Ground-truth JSON format:
    {
        "filename.jpg": {
            "plate_text": "BA1PA0001",
            "plate_type": "embossed"     // or "motorcycle", "devanagari"
        },
        ...
    }

Output:
    Prints a summary table and writes results to
    ml/benchmarks/results/nepali-ocr-<timestamp>.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
from datetime import datetime, timezone


def _cer(gt: str, pred: str) -> float:
    """Levenshtein distance / len(gt), clamped to [0, 1]."""
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


def _best_prediction(image_path: pathlib.Path) -> tuple[str, float]:
    """Run the pipeline OCR on a single image and return (normalised_text, confidence).

    Returns ("", 0.0) when no plate is detected — counted as a miss.
    """
    import cv2
    from drishtiai_pipeline.ocr import detect_plates

    frame = cv2.imread(str(image_path))
    if frame is None:
        return "", 0.0

    detections = detect_plates(frame)
    if not detections:
        return "", 0.0

    best = max(detections, key=lambda d: d.confidence)
    return best.text, best.confidence


def evaluate(image_dir: pathlib.Path, gt_path: pathlib.Path) -> dict:
    gt: dict[str, dict] = json.loads(gt_path.read_text(encoding="utf-8"))

    total = len(gt)
    exact_match = 0
    province_match = 0
    two_row_recall_num = 0
    two_row_recall_den = 0
    cer_sum = 0.0
    misses = 0

    results: list[dict] = []

    for filename, meta in gt.items():
        gt_text: str = meta["plate_text"].upper().replace(" ", "").replace("-", "")
        plate_type: str = meta.get("plate_type", "embossed")

        image_path = image_dir / filename
        if not image_path.exists():
            print(f"  SKIP  {filename} — image not found", file=sys.stderr)
            misses += 1
            continue

        pred_text, confidence = _best_prediction(image_path)

        exact = pred_text == gt_text
        cer = _cer(gt_text, pred_text)
        gt_province = gt_text[:2] if len(gt_text) >= 2 else ""
        pred_province = pred_text[:2] if len(pred_text) >= 2 else ""
        province_ok = gt_province == pred_province and bool(gt_province)

        if exact:
            exact_match += 1
        if province_ok:
            province_match += 1
        cer_sum += cer

        if plate_type == "motorcycle":
            two_row_recall_den += 1
            if exact:
                two_row_recall_num += 1

        results.append({
            "filename": filename,
            "plate_type": plate_type,
            "gt": gt_text,
            "pred": pred_text,
            "confidence": round(confidence, 4),
            "exact_match": exact,
            "cer": round(cer, 4),
        })

    evaluated = total - misses
    if evaluated == 0:
        print("ERROR: no images evaluated — check --image-dir and --gt paths.", file=sys.stderr)
        sys.exit(1)

    summary = {
        "evaluated_at": datetime.now(tz=timezone.utc).isoformat(),
        "total": total,
        "evaluated": evaluated,
        "misses": misses,
        "plate_accuracy": round(exact_match / evaluated, 4),
        "province_accuracy": round(province_match / evaluated, 4),
        "mean_cer": round(cer_sum / evaluated, 4),
        "two_row_recall": round(two_row_recall_num / max(two_row_recall_den, 1), 4),
        "two_row_sample_size": two_row_recall_den,
        "results": results,
    }

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Nepali plate OCR accuracy")
    parser.add_argument("--image-dir", required=True, type=pathlib.Path)
    parser.add_argument("--gt", required=True, type=pathlib.Path)
    parser.add_argument("--out-dir", default="ml/benchmarks/results", type=pathlib.Path)
    args = parser.parse_args()

    print(f"Evaluating {args.image_dir} against {args.gt} …")
    start = time.monotonic()
    summary = evaluate(args.image_dir, args.gt)
    elapsed = time.monotonic() - start

    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%S")
    out_path = out_dir / f"nepali-ocr-{stamp}.json"
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    n = summary["evaluated"]
    print(f"\n{'─' * 40}")
    print(f"  Evaluated:        {n:>6} images  ({elapsed:.1f}s)")
    print(f"  Plate accuracy:   {summary['plate_accuracy'] * 100:>6.1f}%  (target ≥ 92%)")
    print(f"  Mean CER:         {summary['mean_cer'] * 100:>6.1f}%  (target ≤ 8%)")
    print(f"  Province acc.:    {summary['province_accuracy'] * 100:>6.1f}%")
    print(f"  Two-row recall:   {summary['two_row_recall'] * 100:>6.1f}%  (n={summary['two_row_sample_size']},  target ≥ 80%)")
    print(f"{'─' * 40}")
    print(f"\nFull results: {out_path}")


if __name__ == "__main__":
    main()
