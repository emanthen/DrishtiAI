"""
Dominant vehicle color detection via HSV histogram analysis.

Runs on the vehicle body region extracted from the frame (the area
immediately above the plate bounding box).  No ML model required.

Returns a (VehicleColor, confidence) pair or None when the crop is too
small or the dominant colour cannot be determined with confidence ≥ 0.15.
"""
from __future__ import annotations

import cv2
import numpy as np

from drishtiai_shared.models.vehicle import VehicleColor


def detect_color(img: np.ndarray) -> tuple[VehicleColor, float] | None:
    """Detect dominant vehicle body color from a BGR crop.

    Achromatic colours (white/black/silver/grey) are identified via
    value+saturation thresholds.  Chromatic colours are classified by
    dominant hue bin on pixels that exceed a saturation floor.
    """
    if img is None or img.size == 0 or min(img.shape[:2]) < 8:
        return None

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h_ch = hsv[:, :, 0].astype(np.int32)   # 0-179
    s_ch = hsv[:, :, 1]                     # 0-255
    v_ch = hsv[:, :, 2]                     # 0-255

    total: int = h_ch.size

    # ── Achromatic pixel counts ───────────────────────────────────────────────
    white_mask  = (v_ch > 180) & (s_ch < 50)
    black_mask  = v_ch < 45
    silver_mask = (v_ch >= 130) & (v_ch <= 200) & (s_ch < 50) & ~white_mask & ~black_mask
    grey_mask   = (v_ch >= 45) & (v_ch < 130) & (s_ch < 50)

    achromatic: dict[VehicleColor, int] = {
        VehicleColor.white:  int(np.sum(white_mask)),
        VehicleColor.black:  int(np.sum(black_mask)),
        VehicleColor.silver: int(np.sum(silver_mask)),
        VehicleColor.grey:   int(np.sum(grey_mask)),
    }

    # ── Chromatic pixel counts (by hue bin) ───────────────────────────────────
    chroma_mask = (s_ch >= 50) & (v_ch >= 50)
    hue = h_ch[chroma_mask]

    chromatic: dict[VehicleColor, int] = {
        VehicleColor.red:    int(np.sum((hue < 10) | (hue > 160))),
        VehicleColor.orange: int(np.sum((hue >= 10) & (hue < 22))),
        VehicleColor.yellow: int(np.sum((hue >= 22) & (hue < 38))),
        VehicleColor.green:  int(np.sum((hue >= 38) & (hue < 85))),
        VehicleColor.blue:   int(np.sum((hue >= 85) & (hue < 130))),
        VehicleColor.maroon: int(np.sum((hue >= 130) & (hue <= 160))),
    }

    all_counts = {**achromatic, **chromatic}
    winner = max(all_counts, key=all_counts.__getitem__)
    count = all_counts[winner]

    # Require ≥ 15% pixel coverage to declare a winner
    if count < total * 0.15:
        return VehicleColor.other, 0.20

    # Confidence: how dominant is the winner relative to a 50% saturation point
    confidence = min(1.0, count / (total * 0.50))
    return winner, round(float(confidence), 3)
