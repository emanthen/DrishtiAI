# Nepali OCR Benchmark

## Methodology

**Test set:** `ml/benchmarks/synthetic/` — currently placeholder images; real test set is
`ml/benchmarks/nepali_plates_test/` (not yet collected; see Dataset Status below).

**Evaluation script:** `ml/benchmarks/eval_nepali_ocr.py`

**Metrics:**

| Metric | Definition |
|--------|-----------|
| CER | Character Error Rate = (S+D+I) / N at character level |
| Plate Accuracy | Exact-match plate text (after normalisation) |
| Province Accuracy | Correct province prefix extracted |
| Two-Row Recall | % motorcycle plates where two-row split succeeded |

**Evaluation procedure:**

1. Run `python ml/benchmarks/eval_nepali_ocr.py --image-dir <path> --gt ml/benchmarks/phase1_gt.json`
2. Results are written to `ml/benchmarks/results/nepali-ocr-<timestamp>.json`
3. Human-verified corrections from the review queue (`/review-queue`) automatically
   accumulate in `ml/plate-ocr/corrections/`. Run eval again after collecting ≥500
   corrections to measure improvement.

---

## Targets (from spec Part D)

| Metric | Target | Status |
|--------|--------|--------|
| CER — embossed plates | ≤ 8% | **TBD — dataset not yet collected** |
| CER — Devanagari plates | ≤ 15% | **TBD — fine-tuned model blocked on dataset** |
| Plate accuracy — embossed | ≥ 92% | **TBD** |
| Plate accuracy — Devanagari | ≥ 85% | **TBD** |
| Two-row motorcycle recall | ≥ 80% | **TBD** |

---

## Dataset Status

**Blocker:** No labelled Nepali plate dataset exists yet.

The review queue (shipped in PR 2) is the data flywheel:

1. Low-confidence reads (conf 0.40–0.70) appear in `/review-queue`
2. Guards correct or dismiss each item
3. Corrections accumulate in `ml/plate-ocr/corrections/`
4. Target: collect ≥ 500 corrections before attempting a fine-tune run

Estimated timeline to first fine-tune: 2–4 weeks of operational data collection.

---

## Algorithmic Improvements (PR 2, no model required)

Changes that improve accuracy without a fine-tuned model:

- **Motorcycle two-row handling:** aspect-ratio heuristic detects near-square crops,
  splits at midpoint, OCRs each row, recombines. Enables reads of motorcycle plates
  that were previously filtered out entirely by the 1.5× aspect gate.

- **Confidence² voter weighting:** replaces linear confidence with squared confidence
  as the per-frame vote weight. A single high-confidence correct read beats multiple
  low-confidence noise reads.

- **`plate_region` per camera:** guards can tag a camera as `embossed`, `devanagari`,
  or `auto`. Infrastructure for model routing; model selection is deferred to the
  dataset-training PR.
