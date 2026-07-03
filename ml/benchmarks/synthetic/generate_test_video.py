"""
Synthetic Phase 1 test video generator.

Produces a dashcam-style MP4 with realistic licence plates rendered at known
timestamps, and writes a matching ground-truth JSON for the benchmark eval.

Usage:
    uv run python ml/benchmarks/synthetic/generate_test_video.py \
        --output ml/benchmarks/phase1.mp4 \
        --gt     ml/benchmarks/phase1_gt.json \
        --fps 25 --duration 90 --width 1280 --height 720

Requirements: opencv-python-headless, numpy, pillow (all in pipeline deps)
"""
import argparse
import json
import math
import random
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


# ── Plate definitions ──────────────────────────────────────────────────────────

@dataclass
class PlateSpec:
    text: str
    appears_at_s: float
    duration_s: float = 3.0
    format: str = "embossed"
    lane: int = 1               # 0 = left lane, 1 = center, 2 = right
    distance_start: float = 0.6  # 0 = fills frame, 1 = tiny (far away)
    distance_end: float = 0.3    # approaches as time passes

    @property
    def disappears_at_s(self) -> float:
        return self.appears_at_s + self.duration_s


DEFAULT_PLATES = [
    PlateSpec("BA1PA1234",  appears_at_s=3.0,  duration_s=4.0, lane=1),
    PlateSpec("KO2KHA5678", appears_at_s=9.0,  duration_s=3.5, lane=0),
    PlateSpec("LU3JA0001",  appears_at_s=15.0, duration_s=4.0, lane=2),
    PlateSpec("BA1CHA7777", appears_at_s=22.0, duration_s=3.0, lane=1),
    PlateSpec("ME1NA2222",  appears_at_s=28.0, duration_s=4.5, lane=0),
    PlateSpec("RE2CHI8888", appears_at_s=35.0, duration_s=3.0, lane=2),
    PlateSpec("GA1JA4321",  appears_at_s=41.0, duration_s=4.0, lane=1),
    PlateSpec("BA2PA9999",  appears_at_s=48.0, duration_s=3.5, lane=0),
    PlateSpec("KO1KHA3456", appears_at_s=54.0, duration_s=4.0, lane=2),
    PlateSpec("LU1JA1111",  appears_at_s=61.0, duration_s=3.0, lane=1),
    PlateSpec("GA2CHI5555", appears_at_s=68.0, duration_s=4.0, lane=0),
    PlateSpec("ME2NA6666",  appears_at_s=75.0, duration_s=3.5, lane=1),
]


# ── Road background renderer ───────────────────────────────────────────────────

class RoadBackground:
    """Renders a simple moving road background using OpenCV drawing primitives."""

    def __init__(self, width: int, height: int) -> None:
        self.w = width
        self.h = height
        self._rng = random.Random(42)

    def render(self, t: float) -> np.ndarray:
        frame = np.zeros((self.h, self.w, 3), dtype=np.uint8)

        # Sky gradient
        sky_h = int(self.h * 0.35)
        for y in range(sky_h):
            v = int(100 + (155 * y / sky_h))
            frame[y] = [v, int(v * 0.85), int(v * 0.65)]

        # Horizon line
        horizon_y = sky_h
        frame[horizon_y - 2: horizon_y + 2] = [180, 160, 120]

        # Road surface
        for y in range(horizon_y, self.h):
            t_road = (y - horizon_y) / (self.h - horizon_y)
            v = int(55 + 30 * t_road)
            frame[y] = [v, v, v]

        # Road lane markings (dashed centre line)
        cx = self.w // 2
        dash_period = 60
        offset = int(t * 200) % dash_period
        for y in range(horizon_y, self.h, dash_period):
            y_adj = y + offset
            if y_adj + 30 < self.h:
                cv2.line(frame, (cx, y_adj), (cx, y_adj + 30), (220, 220, 180), 3)

        # Edge lane markings (solid white)
        left_x = int(self.w * 0.15)
        right_x = int(self.w * 0.85)
        cv2.line(frame, (left_x, horizon_y), (int(self.w * 0.44), self.h), (200, 200, 180), 3)
        cv2.line(frame, (right_x, horizon_y), (int(self.w * 0.56), self.h), (200, 200, 180), 3)

        # Slight vignette
        vignette = np.ones((self.h, self.w), dtype=np.float32)
        cv2.ellipse(vignette, (self.w // 2, self.h // 2),
                    (int(self.w * 0.55), int(self.h * 0.6)), 0, 0, 360, 0.0, -1)
        vignette = cv2.GaussianBlur(vignette, (0, 0), self.w // 4)
        vignette = np.clip(vignette + 0.6, 0.0, 1.0)
        frame = np.clip(frame * vignette[:, :, np.newaxis], 0, 255).astype(np.uint8)

        return frame


# ── Plate renderer ─────────────────────────────────────────────────────────────

class PlateRenderer:
    """Renders a realistic-looking embossed licence plate onto a frame."""

    PLATE_BG  = (230, 230, 230)  # near-white
    PLATE_FG  = (20,  20,  20)   # near-black text
    PLATE_BORDER = (80, 80, 80)

    def render_onto(
        self,
        frame_bgr: np.ndarray,
        text: str,
        cx: int,
        cy: int,
        scale: float = 1.0,
    ) -> tuple[np.ndarray, tuple[int, int, int, int]]:
        """Draw a plate centred at (cx, cy). Returns (frame, (x,y,w,h)) bbox."""
        h, w = frame_bgr.shape[:2]

        base_w = int(320 * scale)
        base_h = int(80 * scale)
        border  = max(4, int(6 * scale))
        padding = max(4, int(8 * scale))

        plate = Image.new("RGB", (base_w, base_h), self.PLATE_BG)
        draw  = ImageDraw.Draw(plate)

        # Border
        draw.rectangle([0, 0, base_w - 1, base_h - 1], outline=self.PLATE_BORDER, width=border)

        # Try to load a monospace font; fall back to default
        font_size = max(20, int(42 * scale))
        try:
            font = ImageFont.truetype("DejaVuSansMono.ttf", font_size)
        except OSError:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", font_size)
            except OSError:
                font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), text, font=font)
        tx = (base_w - (bbox[2] - bbox[0])) // 2
        ty = (base_h - (bbox[3] - bbox[1])) // 2 - bbox[1]
        draw.text((tx, ty), text, fill=self.PLATE_FG, font=font)

        plate_np = cv2.cvtColor(np.array(plate), cv2.COLOR_RGB2BGR)

        # Position on frame
        x1 = max(0, cx - base_w // 2)
        y1 = max(0, cy - base_h // 2)
        x2 = min(w, x1 + base_w)
        y2 = min(h, y1 + base_h)
        pw, ph = x2 - x1, y2 - y1
        if pw <= 0 or ph <= 0:
            return frame_bgr, (0, 0, 0, 0)

        plate_resized = cv2.resize(plate_np, (pw, ph))

        # Slight perspective warp to feel natural
        if scale < 0.9:
            pts1 = np.float32([[0, 0], [pw, 0], [pw, ph], [0, ph]])
            skew = int(pw * 0.03)
            pts2 = np.float32([[skew, 0], [pw - skew, 0], [pw, ph], [0, ph]])
            M = cv2.getPerspectiveTransform(pts1, pts2)
            plate_resized = cv2.warpPerspective(plate_resized, M, (pw, ph))

        # Blend with frame
        alpha = min(1.0, 0.85 + scale * 0.15)
        roi = frame_bgr[y1:y2, x1:x2]
        blended = cv2.addWeighted(plate_resized, alpha, roi, 1 - alpha, 0)
        frame_bgr = frame_bgr.copy()
        frame_bgr[y1:y2, x1:x2] = blended

        return frame_bgr, (x1, y1, pw, ph)


# ── Vehicle silhouette renderer ────────────────────────────────────────────────

def render_vehicle(frame: np.ndarray, cx: int, bottom_y: int, scale: float) -> np.ndarray:
    """Draw a simple car silhouette behind the plate."""
    w_car = int(340 * scale)
    h_car = int(180 * scale)
    h_cabin = int(80 * scale)

    x1 = cx - w_car // 2
    y_bottom = bottom_y
    y_body_top = y_bottom - h_car
    y_cabin_top = y_body_top - h_cabin

    color = (50, 55, 60)
    # Body
    cv2.rectangle(frame, (x1, y_body_top), (x1 + w_car, y_bottom), color, -1)
    # Cabin
    cabin_l = x1 + int(w_car * 0.15)
    cabin_r = x1 + int(w_car * 0.85)
    cv2.rectangle(frame, (cabin_l, y_cabin_top), (cabin_r, y_body_top), color, -1)
    # Windows (lighter)
    window_color = (80, 90, 100)
    wm = int(w_car * 0.08)
    cv2.rectangle(frame, (cabin_l + wm, y_cabin_top + wm),
                  (cabin_r - wm, y_body_top - wm), window_color, -1)
    # Wheels
    wheel_r = int(35 * scale)
    wy = y_bottom - wheel_r // 2
    cv2.circle(frame, (x1 + int(w_car * 0.2), wy), wheel_r, (25, 25, 25), -1)
    cv2.circle(frame, (x1 + int(w_car * 0.8), wy), wheel_r, (25, 25, 25), -1)
    return frame


# ── Main generator ─────────────────────────────────────────────────────────────

LANE_X_FRACTIONS = [0.28, 0.50, 0.72]
HORIZON_Y_FRACTION = 0.38


def generate(
    output_path: Path,
    gt_path: Path,
    plates: list[PlateSpec],
    fps: int = 25,
    duration_s: float = 90.0,
    width: int = 1280,
    height: int = 720,
) -> None:
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))

    bg = RoadBackground(width, height)
    plate_renderer = PlateRenderer()

    total_frames = int(duration_s * fps)
    horizon_y = int(height * HORIZON_Y_FRACTION)

    print(f"Generating {total_frames} frames ({duration_s}s @ {fps}fps) → {output_path}")
    t0 = time.time()

    for frame_idx in range(total_frames):
        t = frame_idx / fps
        frame = bg.render(t)

        # Draw active plates
        for spec in plates:
            if not (spec.appears_at_s <= t < spec.disappears_at_s):
                continue

            progress = (t - spec.appears_at_s) / spec.duration_s  # 0 → 1
            distance = spec.distance_start + (spec.distance_end - spec.distance_start) * progress
            scale = max(0.25, 1.0 - distance)

            lane_x_frac = LANE_X_FRACTIONS[spec.lane % 3]
            # Vehicles approach from the vanishing point
            vp_x = int(width * 0.50)
            vp_y = horizon_y
            tgt_x = int(width * lane_x_frac)
            tgt_y = int(height * 0.88)

            cx = int(vp_x + (tgt_x - vp_x) * (1 - distance))
            cy = int(vp_y + (tgt_y - vp_y) * (1 - distance))

            frame = render_vehicle(frame, cx, cy + int(30 * scale), scale)

            # Plate sits at the lower front of the vehicle
            plate_cy = cy + int(20 * scale)
            frame, _ = plate_renderer.render_onto(frame, spec.text, cx, plate_cy, scale)

        writer.write(frame)

        if frame_idx % (fps * 5) == 0:
            elapsed = time.time() - t0
            pct = 100 * frame_idx / total_frames
            print(f"  {pct:.0f}%  t={t:.1f}s  elapsed={elapsed:.1f}s")

    writer.release()
    print(f"Video written: {output_path} ({output_path.stat().st_size / 1e6:.1f} MB)")

    # Write ground-truth JSON
    gt = {
        "video": str(output_path.name),
        "fps": fps,
        "duration_s": duration_s,
        "width": width,
        "height": height,
        "expected_plates": [
            {
                "text": p.text,
                "appears_at_s": p.appears_at_s,
                "disappears_at_s": p.disappears_at_s,
                "duration_s": p.duration_s,
                "format": p.format,
                "lane": p.lane,
            }
            for p in plates
        ],
        "acceptance_criteria": {
            "min_recall": 0.90,
            "max_latency_s": 2.0,
            "notes": "90% of plates must appear in the DB within 2s of appearing in stream",
        },
    }
    gt_path.write_text(json.dumps(gt, indent=2))
    print(f"Ground truth written: {gt_path}")
    print(f"\nPlates to detect ({len(plates)}):")
    for p in plates:
        print(f"  {p.text:15s}  {p.appears_at_s:5.1f}s – {p.disappears_at_s:5.1f}s  lane={p.lane}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic Phase 1 test video")
    parser.add_argument("--output",   default="ml/benchmarks/phase1.mp4")
    parser.add_argument("--gt",       default="ml/benchmarks/phase1_gt.json")
    parser.add_argument("--fps",      type=int,   default=25)
    parser.add_argument("--duration", type=float, default=90.0)
    parser.add_argument("--width",    type=int,   default=1280)
    parser.add_argument("--height",   type=int,   default=720)
    args = parser.parse_args()

    output_path = Path(args.output)
    gt_path     = Path(args.gt)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    gt_path.parent.mkdir(parents=True, exist_ok=True)

    generate(
        output_path=output_path,
        gt_path=gt_path,
        plates=DEFAULT_PLATES,
        fps=args.fps,
        duration_s=args.duration,
        width=args.width,
        height=args.height,
    )


if __name__ == "__main__":
    main()
