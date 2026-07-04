"""HTML sanitization for user-supplied free-text fields.

Uses nh3 (Ammonia Rust binding) — strips all HTML tags.
Falls back to a naïve regex if nh3 is unavailable (e.g. CI without Rust libs).
"""
from __future__ import annotations

try:
    import nh3 as _nh3

    def strip_html(text: str) -> str:
        return _nh3.clean(text, tags=set())

except ImportError:
    import re as _re
    _TAG_RE = _re.compile(r"<[^>]+>")

    def strip_html(text: str) -> str:  # type: ignore[misc]
        return _TAG_RE.sub("", text)
