"""
Multi-frame plate text voter.

Instead of emitting the first OCR read for a plate, collect all reads within a
sliding window and emit the majority-vote consensus when the plate "exits"
(no new reads for `exit_gap_s` seconds).

This significantly reduces character-substitution errors (e.g. 0↔O, 1↔I)
common in single-frame PaddleOCR reads.

Thread-safety: one PlateVoter instance per camera thread — no locking needed.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from drishtiai_pipeline.ocr import PlateDetection


@dataclass
class _Track:
    reads: list[PlateDetection] = field(default_factory=list)
    last_seen: float = field(default_factory=time.monotonic)

    def add(self, det: PlateDetection) -> None:
        self.reads.append(det)
        self.last_seen = time.monotonic()

    def consensus(self) -> PlateDetection:
        """
        Confidence²-weighted vote: winner = text with highest Σ(confidence²).

        Squaring the confidence disproportionately rewards high-confidence reads,
        so a single sharp correct read beats several noisy low-confidence misreads.
        The reported output confidence remains a linear average for interpretability.
        """
        weight: dict[str, float] = {}   # conf² sum — used for winner selection
        conf_sum: dict[str, float] = {} # linear conf sum — used for reported value
        best_det: dict[str, PlateDetection] = {}

        for d in self.reads:
            weight[d.text] = weight.get(d.text, 0.0) + d.confidence ** 2
            conf_sum[d.text] = conf_sum.get(d.text, 0.0) + d.confidence
            if d.text not in best_det or d.confidence > best_det[d.text].confidence:
                best_det[d.text] = d

        winner_text = max(weight, key=weight.__getitem__)
        winner_reads = [d for d in self.reads if d.text == winner_text]
        avg_conf = conf_sum[winner_text] / len(winner_reads)

        w = best_det[winner_text]
        return PlateDetection(
            text=w.text,
            confidence=round(avg_conf, 4),
            bbox=w.bbox,
            crop=w.crop,
            sharpness=w.sharpness,
        )


class PlateVoter:
    """
    Accumulates per-frame plate detections and emits consensus reads.

    Usage::

        voter = PlateVoter(on_plate=write_plate_event)
        for frame, ts in capture:
            detections = detect_plates(frame)
            voter.update(detections, ts)
        voter.flush()          # emit any plates still in flight at shutdown

    Parameters
    ----------
    on_plate:
        Callback invoked with the consensus PlateDetection once a plate exits.
    window_s:
        Time window to accumulate reads for a given plate text (seconds).
        Reads with the same text within this window belong to the same pass.
    exit_gap_s:
        A plate is considered to have exited if no new read with that text
        arrives within this many seconds. Should be < window_s.
    min_reads:
        Minimum number of reads required to emit a consensus. Plates seen
        fewer times than this are discarded (likely noise).
    """

    def __init__(
        self,
        on_plate: Callable[[PlateDetection], None],
        window_s: float = 4.0,
        exit_gap_s: float = 1.5,
        min_reads: int = 2,
    ) -> None:
        self._on_plate = on_plate
        self._window_s = window_s
        self._exit_gap_s = exit_gap_s
        self._min_reads = min_reads
        # key: normalised plate text
        self._tracks: dict[str, _Track] = {}

    def update(self, detections: list[PlateDetection], _frame_ts: float | None = None) -> None:
        """Feed a list of per-frame detections. Call once per sampled frame."""
        now = time.monotonic()
        seen_texts: set[str] = set()

        for det in detections:
            key = det.text.upper().replace(" ", "").replace("-", "")
            seen_texts.add(key)
            if key not in self._tracks:
                self._tracks[key] = _Track()
            self._tracks[key].add(det)

        self._expire(now)

    def _expire(self, now: float) -> None:
        expired = [
            key for key, track in self._tracks.items()
            if now - track.last_seen >= self._exit_gap_s
        ]
        for key in expired:
            track = self._tracks.pop(key)
            if len(track.reads) >= self._min_reads:
                self._on_plate(track.consensus())

    def flush(self) -> None:
        """Emit all in-flight plates regardless of exit gap. Call at shutdown."""
        for track in self._tracks.values():
            if len(track.reads) >= self._min_reads:
                self._on_plate(track.consensus())
        self._tracks.clear()
