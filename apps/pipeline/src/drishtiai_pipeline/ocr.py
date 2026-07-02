"""
Plate OCR using PaddleOCR.

Phase 1: PaddleOCR's general text detection + recognition on the full frame.
         We filter results by aspect ratio and text length to isolate plate-like regions.
Phase 3: Replace with fine-tuned plate detector + Devanagari-capable OCR model.
"""
import logging
import re
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)

# Lazy-loaded — PaddleOCR takes ~3s to initialize on first call
_ocr = None


def _get_ocr():
    global _ocr
    if _ocr is None:
        from paddleocr import PaddleOCR
        logger.info("Initializing PaddleOCR (first load, may take a few seconds)...")
        _ocr = PaddleOCR(
            use_angle_cls=True,
            lang="en",
            show_log=False,
            use_gpu=False,   # Phase 1: CPU. Phase 2+: set from config/GPU availability.
        )
        logger.info("PaddleOCR ready.")
    return _ocr


@dataclass
class PlateDetection:
    text: str
    confidence: float
    bbox: list[list[float]]  # [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
    crop: np.ndarray          # BGR crop of the plate region


# Regex for English/Latin vehicle plates (very broad — covers NP, IN, and generic formats)
_PLATE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9\s\-]{2,14}[A-Z0-9]$")

# Plate region aspect ratio: width/height typically 2.0–7.0 for standard plates
_MIN_ASPECT = 1.5
_MAX_ASPECT = 8.0

# Minimum plate region area in pixels
_MIN_AREA = 800


def detect_plates(frame_bgr: np.ndarray) -> list[PlateDetection]:
    """
    Run PaddleOCR on a full frame and return plate-like detections.
    Filters by aspect ratio, text length, and a permissive alphanumeric pattern.
    """
    ocr = _get_ocr()
    try:
        results = ocr.ocr(frame_bgr, cls=True)
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

        # bbox_raw: [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
        xs = [p[0] for p in bbox_raw]
        ys = [p[1] for p in bbox_raw]
        w = max(xs) - min(xs)
        h = max(ys) - min(ys)
        area = w * h

        if area < _MIN_AREA:
            continue

        aspect = w / max(h, 1)
        if not (_MIN_ASPECT <= aspect <= _MAX_ASPECT):
            continue

        clean = text.upper().replace(" ", "").replace(".", "").replace("-", "")
        if len(clean) < 3 or len(clean) > 12:
            continue

        if not _PLATE_PATTERN.match(clean):
            continue

        x1, y1 = int(min(xs)), int(min(ys))
        x2, y2 = int(max(xs)), int(max(ys))
        crop = frame_bgr[max(0, y1):y2, max(0, x1):x2]

        plates.append(PlateDetection(
            text=clean,
            confidence=float(confidence),
            bbox=bbox_raw,
            crop=crop,
        ))

    return plates
