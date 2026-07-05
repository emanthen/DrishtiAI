"""
Plate OCR — Phase 11: two-stage detection + pre-processing + char correction.

Pipeline
--------
1. Candidate localisation (two-stage, optional)
   OpenCV Sobel → dilate → contours → aspect/area filter → candidate bboxes
   Falls back to full-frame OCR when no candidates found.

2. Crop pre-processing (optional)
   CLAHE contrast enhancement + unsharp-mask sharpening + minimum-height upscale.
   Dramatically improves accuracy on underexposed or motion-blurred frames.

3. PaddleOCR recognition
   Runs on pre-processed crop (fast) or full frame (fallback).
   GPU controlled by PIPELINE_OCR_USE_GPU env / config flag.

4. Post-OCR correction
   Context-free character substitution table for common plate OCR errors
   (0/O, 1/I, 5/S, 8/B, 6/G, 2/Z).  Position-aware: leading alpha-run
   gets digit→letter corrections; trailing digit-run gets letter→digit
   corrections; mixed-middle section gets no correction.

5. Nepal plate normaliser
   Detects known province-code prefixes (Ba, Ko, Ma, Ga, Lu, Ka, Su) and
   reformats to a canonical `BA1PA0001` (no spaces, uppercase) form used
   for watchlist matching.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import cv2
import numpy as np

from drishtiai_pipeline.config import settings

logger = logging.getLogger(__name__)

# Lazy-loaded — PaddleOCR takes ~3 s to initialize on first call
_ocr = None


def _get_ocr():
    global _ocr
    if _ocr is None:
        from paddleocr import PaddleOCR
        logger.info("Initialising PaddleOCR (first load)…")
        _ocr = PaddleOCR(
            use_angle_cls=True,
            lang="en",
            show_log=False,
            use_gpu=settings.pipeline_ocr_use_gpu,
        )
        logger.info("PaddleOCR ready (gpu=%s).", settings.pipeline_ocr_use_gpu)
    return _ocr


# ── Constants ─────────────────────────────────────────────────────────────────

# Lowered from 1.5 to 0.8 to capture two-row motorcycle plates (nearly square).
# Single-row candidates still dominate; two-row detection path runs only for
# aspect ratios below _MOTO_ASPECT_MAX.
_MIN_ASPECT       = 0.8   # width / height — was 1.5
_MAX_ASPECT       = 8.0
_MOTO_ASPECT_MAX  = 1.5   # below this aspect ratio → attempt two-row split first
_MIN_AREA         = 800   # pixels²
_PAD              = 8     # pixels of padding added around each candidate crop
_MIN_CROP_H       = 32    # PaddleOCR works best when text height ≥ 32 px

# Broad alphanumeric pattern: 3–13 chars, starts + ends with alnum
_PLATE_RE = re.compile(r"^[A-Z0-9][A-Z0-9]{1,11}[A-Z0-9]$")

# Nepal province code prefixes (Latin OCR transliterations)
_NP_PREFIXES = ("BA", "KO", "MA", "GA", "LU", "KA", "SU", "ME", "NA")


# ── Stage 1 — candidate localisation ─────────────────────────────────────────

def _find_plate_candidates(
    frame: np.ndarray,
) -> list[tuple[int, int, int, int]]:
    """
    Use Sobel edges + horizontal dilation + contour filtering to find regions
    that look like licence plates.  Returns (x1, y1, x2, y2) tuples with
    padding applied; may return an empty list.
    """
    h_frame, w_frame = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Bilateral filter: reduces noise while keeping edges sharp
    smooth = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)

    # Horizontal Sobel — plates are character-rich horizontal structures
    sobel = cv2.Sobel(smooth, cv2.CV_8U, 1, 0, ksize=3)

    # Otsu threshold on the edge map
    _, thresh = cv2.threshold(sobel, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

    # Dilate horizontally to connect individual characters into a plate blob
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (17, 3))
    dilated = cv2.dilate(thresh, kernel)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates: list[tuple[int, int, int, int]] = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if w * h < _MIN_AREA:
            continue
        aspect = w / max(h, 1)
        if not (_MIN_ASPECT <= aspect <= _MAX_ASPECT):
            continue
        x1 = max(0, x - _PAD)
        y1 = max(0, y - _PAD)
        x2 = min(w_frame, x + w + _PAD)
        y2 = min(h_frame, y + h + _PAD)
        candidates.append((x1, y1, x2, y2))

    return candidates


# ── Stage 2 — crop pre-processing ────────────────────────────────────────────

def _preprocess_crop(crop: np.ndarray) -> np.ndarray:
    """
    CLAHE contrast enhancement + unsharp-mask sharpening + upscale if tiny.
    Returns a BGR image ready for PaddleOCR.
    """
    if crop.size == 0:
        return crop

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop.copy()

    # Upscale very small crops so PaddleOCR can resolve individual characters
    h, w = gray.shape[:2]
    if h < _MIN_CROP_H:
        scale = _MIN_CROP_H / h
        gray = cv2.resize(
            gray, (max(1, int(w * scale)), _MIN_CROP_H), interpolation=cv2.INTER_CUBIC
        )

    # CLAHE — equalises contrast locally; good for harsh shadows and night shots
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
    enhanced = clahe.apply(gray)

    # Unsharp mask — recovers some sharpness lost to motion blur
    blurred = cv2.GaussianBlur(enhanced, (0, 0), sigmaX=2)
    sharpened = cv2.addWeighted(enhanced, 1.5, blurred, -0.5, 0)

    return cv2.cvtColor(sharpened, cv2.COLOR_GRAY2BGR)


# ── Stage 4 — post-OCR correction ────────────────────────────────────────────

# Characters that look alike and are commonly swapped
_LETTER_TO_DIGIT = str.maketrans("OILSZGB", "0115260")  # in digit run: O→0 etc.
_DIGIT_TO_LETTER = str.maketrans("015260",  "OILSZG")   # in letter run: 0→O etc.


def _correct_chars(text: str) -> str:
    """
    Position-aware character substitution.

    Splits the cleaned plate text into three zones:
      • leading alpha run  — expect letters; convert stray digits → letters
      • trailing digit run — expect digits; convert stray letters → digits
      • middle remainder   — leave untouched (too ambiguous)

    Example: "BA1PA0O01" → correct trailing run "0O01" → "0001"
             result: "BA1PA0001"
    """
    if not text:
        return text

    # Leading alpha zone
    lead_end = 0
    while lead_end < len(text) and text[lead_end].isalpha():
        lead_end += 1

    # Trailing digit zone
    trail_start = len(text)
    while trail_start > lead_end and text[trail_start - 1].isdigit():
        trail_start -= 1

    lead   = text[:lead_end].translate(_DIGIT_TO_LETTER)
    middle = text[lead_end:trail_start]
    trail  = text[trail_start:].translate(_LETTER_TO_DIGIT)

    return lead + middle + trail


def _normalize_np_plate(text: str) -> str | None:
    """
    If `text` looks like a Nepal province plate, return its canonical form
    (uppercase, no spaces/dashes, province code corrected).

    Returns None if it does not match any known Nepal plate pattern.

    Nepal format: [province2-3][series1-2][type1-2][vehicle4-5]
    Example: BA1PA0001, KO2NA3456
    """
    upper = text.upper()

    # Must start with a known province prefix
    prefix = next((p for p in _NP_PREFIXES if upper.startswith(p)), None)
    if prefix is None:
        return None

    rest = upper[len(prefix):]

    # Next: 1-2 digit series
    m = re.match(r"^(\d{1,2})([A-Z]{1,2})(\d{4,5})$", rest)
    if not m:
        return None

    series, vtype, number = m.groups()
    return f"{prefix}{series}{vtype}{number.zfill(4)}"


# ── Main entry point ──────────────────────────────────────────────────────────

@dataclass
class PlateDetection:
    text: str
    confidence: float
    bbox: list[list[float]]   # [[x1,y1],[x2,y1],[x2,y2],[x1,y2]] in frame coords
    crop: np.ndarray           # BGR crop of the plate region (pre-processed)
    sharpness: float = 0.0    # Laplacian variance — higher = sharper frame


def _measure_sharpness(img: np.ndarray) -> float:
    """Laplacian variance as a proxy for focus quality."""
    if img is None or img.size == 0:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _raw_ocr_text(image: np.ndarray) -> tuple[str, float] | None:
    """Run PaddleOCR; return (cleaned_text, confidence) for the highest-confidence line.

    No plate-RE filtering — used for individual rows of a two-row motorcycle crop.
    """
    if image is None or image.size == 0:
        return None
    ocr = _get_ocr()
    try:
        results = ocr.ocr(image, cls=True)
    except Exception:
        return None
    if not results or results[0] is None:
        return None
    best = max(
        (line for line in results[0] if line is not None),
        key=lambda l: l[1][1],
        default=None,
    )
    if best is None:
        return None
    text, conf = best[1]
    clean = text.upper().replace(" ", "").replace(".", "").replace("-", "")
    return clean, float(conf)


def _try_two_row(crop: np.ndarray, offset_x: int, offset_y: int) -> PlateDetection | None:
    """Split a near-square crop horizontally and combine the two OCR rows.

    Nepal motorcycle plates have two rows (e.g. top="BA1PA", bottom="0001").
    Single-row OCR on the full crop usually fails; splitting succeeds because
    each row has a sensible text-height-to-width ratio.
    """
    h, w = crop.shape[:2]
    if h < 20 or w < 20:
        return None

    mid = h // 2
    top_proc = _preprocess_crop(crop[:mid, :])
    bot_proc = _preprocess_crop(crop[mid:, :])

    top = _raw_ocr_text(top_proc)
    bot = _raw_ocr_text(bot_proc)

    if top is None or bot is None:
        return None

    combined = _correct_chars(top[0] + bot[0])
    normalised = _normalize_np_plate(combined)
    if normalised is None:
        return None

    avg_conf = (top[1] + bot[1]) / 2.0
    if avg_conf < 0.30:
        return None

    bbox = [
        [offset_x, offset_y],
        [offset_x + w, offset_y],
        [offset_x + w, offset_y + h],
        [offset_x, offset_y + h],
    ]
    return PlateDetection(
        text=normalised,
        confidence=round(avg_conf, 4),
        bbox=bbox,
        crop=crop,
        sharpness=_measure_sharpness(crop),
    )


def _run_ocr_on_image(
    image: np.ndarray,
    offset_x: int = 0,
    offset_y: int = 0,
) -> list[PlateDetection]:
    """Run PaddleOCR on `image`, apply filters, return PlateDetections.

    `offset_x/y` translate bbox coordinates back to full-frame space.
    """
    ocr = _get_ocr()
    try:
        results = ocr.ocr(image, cls=True)
    except Exception:
        logger.exception("PaddleOCR inference failed")
        return []

    if not results or results[0] is None:
        return []

    plates: list[PlateDetection] = []
    for line in results[0]:
        if line is None:
            continue
        bbox_raw, (text, confidence) = line
        if confidence < 0.3:
            continue

        xs = [p[0] for p in bbox_raw]
        ys = [p[1] for p in bbox_raw]
        w = max(xs) - min(xs)
        h = max(ys) - min(ys)

        if w * h < _MIN_AREA:
            continue

        aspect = w / max(h, 1)
        if not (_MIN_ASPECT <= aspect <= _MAX_ASPECT):
            continue

        # Clean and correct
        clean = text.upper().replace(" ", "").replace(".", "").replace("-", "")
        clean = _correct_chars(clean)

        if len(clean) < 3 or len(clean) > 13:
            continue
        if not _PLATE_RE.match(clean):
            continue

        # Try Nepal normalisation; keep original if it doesn't match
        normalised = _normalize_np_plate(clean) or clean

        # Translate bbox back to full-frame coords
        frame_bbox = [
            [p[0] + offset_x, p[1] + offset_y] for p in bbox_raw
        ]

        # Crop from the image passed in (not full frame — caller handles that)
        x1c, y1c = int(min(xs)), int(min(ys))
        x2c, y2c = int(max(xs)), int(max(ys))
        crop = image[max(0, y1c):y2c, max(0, x1c):x2c]

        plates.append(PlateDetection(
            text=normalised,
            confidence=float(confidence),
            bbox=frame_bbox,
            crop=crop,
            sharpness=_measure_sharpness(crop),
        ))

    return plates


def detect_plates(frame_bgr: np.ndarray) -> list[PlateDetection]:
    """
    Run the full two-stage OCR pipeline on a BGR frame.

    Returns a deduplicated list of PlateDetections sorted by confidence (desc).
    """
    results: list[PlateDetection] = []

    if settings.pipeline_ocr_two_stage:
        candidates = _find_plate_candidates(frame_bgr)
    else:
        candidates = []

    if candidates:
        for x1, y1, x2, y2 in candidates:
            crop = frame_bgr[y1:y2, x1:x2]
            if crop.size == 0:
                continue

            crop_h, crop_w = crop.shape[:2]
            aspect = crop_w / max(crop_h, 1)

            # Near-square crop → likely a two-row motorcycle plate.
            # Try two-row split first; fall through to single-row OCR as fallback.
            if aspect < _MOTO_ASPECT_MAX:
                moto = _try_two_row(crop, offset_x=x1, offset_y=y1)
                if moto is not None:
                    results.append(moto)
                    continue  # don't also run single-row on this candidate

            processed = _preprocess_crop(crop) if settings.pipeline_ocr_preprocess else crop
            found = _run_ocr_on_image(processed, offset_x=x1, offset_y=y1)
            results.extend(found)
    else:
        # Fallback: full-frame OCR (slower, more false positives)
        if settings.pipeline_ocr_preprocess:
            # Pre-process a downscaled copy to keep latency manageable
            h, w = frame_bgr.shape[:2]
            scale = min(1.0, 1280 / max(w, 1))
            small = cv2.resize(frame_bgr, (int(w * scale), int(h * scale))) if scale < 1.0 else frame_bgr
        else:
            small = frame_bgr

        results = _run_ocr_on_image(small)

    # Deduplicate: keep highest-confidence result per normalised text
    best: dict[str, PlateDetection] = {}
    for det in results:
        if det.text not in best or det.confidence > best[det.text].confidence:
            best[det.text] = det

    return sorted(best.values(), key=lambda d: d.confidence, reverse=True)
