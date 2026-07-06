"""
Generate a labelled static-image crop dataset for OCR benchmark evaluation.

Produces individual JPEG crops of synthetic Nepali plates under varied
conditions (blur, noise, perspective, brightness, nighttime) and a matching
ground-truth JSON file.

Usage:
    uv run python ml/benchmarks/synthetic/generate_plate_crops.py \
        --out-dir  ml/benchmarks/nepali_plates_test/ \
        --gt       ml/benchmarks/nepali_gt.json \
        --count    500 \
        --seed     42

The output is:
    ml/benchmarks/nepali_plates_test/<filename>.jpg   — plate crop image
    ml/benchmarks/nepali_gt.json                      — ground-truth labels

Ground-truth JSON format (matches eval_nepali_ocr.py):
    {
        "00001_BA1PA1234.jpg": {
            "plate_text":  "BA1PA1234",
            "plate_type":  "embossed",
            "condition":   "clean"
        },
        ...
    }

Augmentation conditions applied:
    clean       — white background, black text, no noise
    blur        — Gaussian blur sigma 1.5–3.0
    noise       — salt-and-pepper + Gaussian noise
    perspective — random perspective warp (max 12-degree tilt)
    night       — simulated nighttime (dark background, yellow plate tint)
    combined    — blur + noise + perspective together

Plate types:
    embossed    — standard Nepali format e.g. BA 1 PA 0001
    motorcycle  — two-row format (province+district on row 1, number on row 2)
    devanagari  — Devanagari numeral prefix (for government vehicles)
"""
from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# ── Nepali plate character pools ──────────────────────────────────────────────

PROVINCE_CODES = ["BA", "KO", "LU", "GA", "ME", "RE", "SU"]
DISTRICT_CODES = [
    "PA", "KHA", "JA", "CHA", "NA", "CHI", "NE", "TH", "RA", "PHA",
    "MA", "LAM", "KA", "SI", "GA", "DHA", "BI", "MU",
]
# Devanagari digits ०–९
DEV_DIGITS = "०१२३४५६७८९"

CONDITIONS = ["clean", "blur", "noise", "perspective", "night", "combined"]
CONDITION_WEIGHTS = [0.25, 0.20, 0.15, 0.15, 0.10, 0.15]

PLATE_W, PLATE_H = 360, 90   # crop resolution for embossed
MOTO_W,  MOTO_H  = 200, 130  # motorcycle two-row crop


def _random_plate_text(rng: random.Random) -> tuple[str, str]:
    """Return (normalised_text, plate_type)."""
    ptype = rng.choices(
        ["embossed", "motorcycle", "devanagari"],
        weights=[0.65, 0.25, 0.10],
    )[0]
    province = rng.choice(PROVINCE_CODES)
    pnum = rng.randint(1, 7)
    district = rng.choice(DISTRICT_CODES)
    number = rng.randint(1, 9999)
    if ptype == "devanagari":
        # Devanagari government plate: e.g. ब.ग.०१.०२३४ → normalised BA1PA0023
        # We store the canonical normalised form; OCR output is compared after
        # normalisation so both Devanagari and Latin representations match.
        digits = "".join(DEV_DIGITS[int(d)] for d in f"{number:04d}")
        text = f"{province}{pnum}{district}{number:04d}"
    else:
        text = f"{province}{pnum}{district}{number:04d}"
    return text, ptype


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "DejaVuSansMono-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeMono.ttf",
        "FreeMono.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _render_embossed(text: str, w: int = PLATE_W, h: int = PLATE_H) -> np.ndarray:
    img = Image.new("RGB", (w, h), (255, 252, 220))  # pale yellow plate
    draw = ImageDraw.Draw(img)
    font = _load_font(max(24, h - 20))
    # Centre text
    bbox = draw.textbbox((0, 0), text, font=font)
    tx = (w - (bbox[2] - bbox[0])) // 2
    ty = (h - (bbox[3] - bbox[1])) // 2
    # Embossed shadow
    draw.text((tx + 2, ty + 2), text, fill=(80, 80, 80), font=font)
    draw.text((tx, ty), text, fill=(10, 10, 10), font=font)
    # Border
    draw.rectangle([(2, 2), (w - 3, h - 3)], outline=(30, 30, 30), width=3)
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def _render_motorcycle(text: str) -> np.ndarray:
    """Split text at half-point and render two-row plate."""
    mid = len(text) // 2
    row1, row2 = text[:mid], text[mid:]
    w, h = MOTO_W, MOTO_H
    img = Image.new("RGB", (w, h), (255, 252, 220))
    draw = ImageDraw.Draw(img)
    font = _load_font(max(18, h // 3 - 4))
    for i, row in enumerate([row1, row2]):
        bbox = draw.textbbox((0, 0), row, font=font)
        tx = (w - (bbox[2] - bbox[0])) // 2
        ty = 10 + i * (h // 2)
        draw.text((tx + 2, ty + 2), row, fill=(80, 80, 80), font=font)
        draw.text((tx, ty), row, fill=(10, 10, 10), font=font)
    draw.rectangle([(2, 2), (w - 3, h - 3)], outline=(30, 30, 30), width=3)
    draw.line([(2, h // 2), (w - 3, h // 2)], fill=(100, 100, 100), width=1)
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def _render_devanagari(text: str, w: int = PLATE_W, h: int = PLATE_H) -> np.ndarray:
    """Devanagari plate: render with numeric suffix in Devanagari digits."""
    # Convert trailing digits to Devanagari for visual realism
    suffix_digits = re.search(r"\d+$", text)
    display = text
    if suffix_digits:
        dev_suffix = "".join(DEV_DIGITS[int(d)] for d in suffix_digits.group())
        display = text[:suffix_digits.start()] + dev_suffix
    img = Image.new("RGB", (w, h), (240, 240, 255))  # pale blue for govt
    draw = ImageDraw.Draw(img)
    font = _load_font(max(20, h - 24))
    bbox = draw.textbbox((0, 0), display, font=font)
    tx = (w - (bbox[2] - bbox[0])) // 2
    ty = (h - (bbox[3] - bbox[1])) // 2
    draw.text((tx + 2, ty + 2), display, fill=(80, 80, 100), font=font)
    draw.text((tx, ty), display, fill=(0, 0, 80), font=font)
    draw.rectangle([(2, 2), (w - 3, h - 3)], outline=(0, 0, 120), width=3)
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


# ── Augmentations ─────────────────────────────────────────────────────────────

def _blur(img: np.ndarray, rng: random.Random) -> np.ndarray:
    sigma = rng.uniform(1.5, 3.0)
    k = int(sigma * 6) | 1  # must be odd
    return cv2.GaussianBlur(img, (k, k), sigma)


def _noise(img: np.ndarray, rng: random.Random) -> np.ndarray:
    out = img.astype(np.float32)
    # Gaussian noise
    out += np.random.normal(0, rng.uniform(5, 20), out.shape).astype(np.float32)
    # Salt and pepper
    n_sp = int(img.size * rng.uniform(0.002, 0.01))
    for _ in range(n_sp):
        r, c = rng.randint(0, img.shape[0] - 1), rng.randint(0, img.shape[1] - 1)
        out[r, c] = 255 if rng.random() > 0.5 else 0
    return np.clip(out, 0, 255).astype(np.uint8)


def _perspective(img: np.ndarray, rng: random.Random) -> np.ndarray:
    h, w = img.shape[:2]
    max_d = int(min(h, w) * 0.12)
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = src + np.float32([
        [rng.randint(-max_d, max_d), rng.randint(-max_d, max_d)]
        for _ in range(4)
    ])
    M = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(img, M, (w, h), borderMode=cv2.BORDER_REPLICATE)


def _night(img: np.ndarray, rng: random.Random) -> np.ndarray:
    """Simulate nighttime illumination: dark surroundings, yellowish plate glow."""
    out = img.astype(np.float32)
    # Darken + add orange/yellow tint (headlight illumination)
    brightness = rng.uniform(0.5, 0.8)
    out *= brightness
    tint = np.zeros_like(out)
    tint[:, :, 2] = rng.uniform(20, 50)   # R
    tint[:, :, 1] = rng.uniform(10, 30)   # G
    out = np.clip(out + tint, 0, 255)
    return _noise(out.astype(np.uint8), rng)


def _augment(img: np.ndarray, condition: str, rng: random.Random) -> np.ndarray:
    if condition == "clean":
        return img
    elif condition == "blur":
        return _blur(img, rng)
    elif condition == "noise":
        return _noise(img, rng)
    elif condition == "perspective":
        return _perspective(img, rng)
    elif condition == "night":
        return _night(img, rng)
    elif condition == "combined":
        img = _perspective(img, rng)
        img = _blur(img, rng)
        img = _noise(img, rng)
        return img
    return img


# ── Main ──────────────────────────────────────────────────────────────────────

def generate(
    out_dir: Path,
    gt_path: Path,
    count: int = 500,
    seed: int = 42,
) -> None:
    rng = random.Random(seed)
    np.random.seed(seed)
    out_dir.mkdir(parents=True, exist_ok=True)

    gt: dict[str, dict] = {}

    for i in range(count):
        text, ptype = _random_plate_text(rng)
        condition = rng.choices(CONDITIONS, weights=CONDITION_WEIGHTS)[0]

        if ptype == "motorcycle":
            base_img = _render_motorcycle(text)
        elif ptype == "devanagari":
            base_img = _render_devanagari(text)
        else:
            base_img = _render_embossed(text)

        img = _augment(base_img, condition, rng)

        filename = f"{i + 1:05d}_{text}_{condition}.jpg"
        filepath = out_dir / filename
        cv2.imwrite(str(filepath), img, [cv2.IMWRITE_JPEG_QUALITY, 92])

        gt[filename] = {
            "plate_text": text,
            "plate_type": ptype,
            "condition": condition,
        }

    gt_path.parent.mkdir(parents=True, exist_ok=True)
    gt_path.write_text(json.dumps(gt, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Generated {count} plate crops → {out_dir}")
    print(f"Ground truth → {gt_path}")
    counts = {}
    for v in gt.values():
        key = f"{v['plate_type']}/{v['condition']}"
        counts[key] = counts.get(key, 0) + 1
    for k, v in sorted(counts.items()):
        print(f"  {k}: {v}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic Nepali plate crops")
    parser.add_argument("--out-dir", default="ml/benchmarks/nepali_plates_test", type=Path)
    parser.add_argument("--gt",      default="ml/benchmarks/nepali_gt.json",      type=Path)
    parser.add_argument("--count",   default=500, type=int)
    parser.add_argument("--seed",    default=42,  type=int)
    args = parser.parse_args()
    generate(args.out_dir, args.gt, args.count, args.seed)


if __name__ == "__main__":
    main()
