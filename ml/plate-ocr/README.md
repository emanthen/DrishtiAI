# Plate OCR

Fine-tuned PaddleOCR models for Nepali embossed and Devanagari plates.

## Models

| Model | Base | License | Distribution |
|-------|------|---------|-------------|
| `embossed-latin-v1` | PaddleOCR | Apache-2.0 | Included in release |
| `devanagari-v1` | PaddleOCR | Apache-2.0 | Included in release |

## Target accuracy (Phase 3)

- Embossed Latin: ≥ 92% CER daytime, ≥ 85% nighttime
- Devanagari: ≥ 85% CER daytime, ≥ 75% nighttime
- Motorcycle (two-row): ≥ 80% CER daytime

## Dataset

Collect ~5,000 embossed + ~5,000 Devanagari plate crops. Labeled with plate text.
Stored at `ml/plate-ocr/data/` (excluded from git — use DVC or direct download script).

## Corrections

Guard-corrected reads from the review queue land in `ml/plate-ocr/corrections/` as:
```
{crop_id}.jpg   — the plate crop
{crop_id}.txt   — the correct text
```
