# ML Benchmarks

Reproducible evaluation scripts and results. All results checked into this directory.

## Test assets

| File | Description | Ground truth |
|------|-------------|-------------|
| `phase1.mp4` | English/embossed plates, mixed conditions | `phase1_gt.json` |
| `nepali_plates_test/` | Nepali Devanagari + embossed test set | `nepali_gt.json` |
| `analytics_test/` | Labeled clips for wrong-way, illegal park, etc. | `analytics_gt.json` |

## How to run

```bash
# Phase 1 plate read benchmark
uv run python ml/benchmarks/eval_plate_read.py --video ml/benchmarks/phase1.mp4 --gt ml/benchmarks/phase1_gt.json

# Phase 3 OCR accuracy
uv run python ml/benchmarks/eval_ocr.py --dataset ml/benchmarks/nepali_plates_test/
```

## Results (updated per phase)

| Phase | Model | Metric | Target | Result |
|-------|-------|--------|--------|--------|
| 1 | RT-DETR-R18 + PaddleOCR base | Plate read rate | ≥ 90% | — |
| 3 | Fine-tuned embossed | CER daytime | ≥ 92% | — |
| 3 | Fine-tuned Devanagari | CER daytime | ≥ 85% | — |
| 4 | Vehicle type classifier | Top-1 accuracy | ≥ 95% | — |
