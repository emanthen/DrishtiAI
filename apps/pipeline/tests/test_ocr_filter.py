"""
Unit tests for the OCR plate filter logic (no GPU required).
Tests the regex and aspect-ratio filtering without running PaddleOCR.
"""
import re
import pytest

# Mirror the filter logic from ocr.py
_PLATE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9\s\-]{2,14}[A-Z0-9]$")
_MIN_ASPECT = 1.5
_MAX_ASPECT = 8.0


def _is_plate_candidate(text: str, w: float, h: float) -> bool:
    clean = text.upper().replace(" ", "").replace(".", "").replace("-", "")
    if len(clean) < 3 or len(clean) > 12:
        return False
    if not _PLATE_PATTERN.match(clean):
        return False
    aspect = w / max(h, 1)
    return _MIN_ASPECT <= aspect <= _MAX_ASPECT


@pytest.mark.parametrize("text,w,h,expected", [
    ("BA 1 PA 1234", 200, 50, True),   # Nepali-style, good aspect
    ("GA 1 JA 9999", 180, 45, True),
    ("Hello World", 200, 50, False),   # not alphanumeric enough
    ("AB", 200, 50, False),            # too short
    ("AB1234", 100, 100, False),       # square — bad aspect
    ("ABCDEFGHIJKLMN", 200, 50, False),# too long
])
def test_plate_filter(text: str, w: float, h: float, expected: bool) -> None:
    assert _is_plate_candidate(text, w, h) == expected
