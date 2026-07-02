"""
Deduplication: suppress repeated reads of the same plate within N seconds.
Simple in-memory dict; per-camera instances are created in main.py.
"""
import time


class PlateDeduplicator:
    def __init__(self, window_seconds: int = 5) -> None:
        self._window = window_seconds
        self._last_seen: dict[str, float] = {}

    def is_new(self, plate_text: str) -> bool:
        now = time.monotonic()
        last = self._last_seen.get(plate_text, 0.0)
        if now - last >= self._window:
            self._last_seen[plate_text] = now
            return True
        return False

    def reset(self) -> None:
        self._last_seen.clear()
