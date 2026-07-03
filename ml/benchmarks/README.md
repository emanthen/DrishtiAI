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
# Generate synthetic Phase 1 test video (run once)
make generate-test-video
# or manually:
uv run python ml/benchmarks/synthetic/generate_test_video.py \
    --output ml/benchmarks/phase1.mp4 \
    --gt ml/benchmarks/phase1_gt.json

# Evaluate Phase 1 recall (run after 'make dev' + pipeline has processed the video)
make benchmark
# or manually, with custom video-start timestamp:
uv run python ml/benchmarks/eval_phase1.py \
    --gt ml/benchmarks/phase1_gt.json \
    --video-start 2026-07-03T10:00:00Z

# Phase 3 OCR accuracy (Phase 3)
uv run python ml/benchmarks/eval_ocr.py --dataset ml/benchmarks/nepali_plates_test/
```

## Results (updated per phase)

| Phase | Model | Metric | Target | Result |
|-------|-------|--------|--------|--------|
| 1 | RT-DETR-R18 + PaddleOCR base | Plate read rate | ≥ 90% | — |
| 3 | Fine-tuned embossed | CER daytime | ≥ 92% | — |
| 3 | Fine-tuned Devanagari | CER daytime | ≥ 85% | — |
| 4 | Vehicle type classifier | Top-1 accuracy | ≥ 95% | — |
