"""
Clock-rollback guard — detects system clock being set backwards.

A signed last-seen file (HMAC-SHA256, keyed on license_id) stores the last
observed UTC timestamp. On each check, if the new time is more than
ROLLBACK_THRESHOLD_S seconds behind the stored time we raise ClockTamperError.

The key is derived from license_id so the guard resets automatically when a
new license is issued, preventing false positives on legitimate re-installs.

The guard file itself cannot be committed to revision control because it lives
at runtime under /var/lib/drishtiai/ (or configured by env). Deleting it
counts as a rollback by design — the next write will re-anchor to "now".
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import struct
import time
from pathlib import Path

log = logging.getLogger(__name__)

ROLLBACK_THRESHOLD_S = 120  # 2 minutes — tolerates NTP corrections


class ClockTamperError(Exception):
    """Raised when the system clock appears to have been rolled back."""


def _derive_key(license_id: str) -> bytes:
    """Deterministic key from license_id — 32 bytes, no stored secret needed."""
    return hashlib.sha256(f"drishti-clockguard:{license_id}".encode()).digest()


def _sign(timestamp: float, license_id: str) -> bytes:
    key = _derive_key(license_id)
    payload = struct.pack(">d", timestamp)
    return hmac.new(key, payload, hashlib.sha256).digest()


def _verify(timestamp: float, sig: bytes, license_id: str) -> bool:
    expected = _sign(timestamp, license_id)
    return hmac.compare_digest(expected, sig)


def check_and_update(guard_file: Path, license_id: str, *, _now: float | None = None) -> None:
    """
    Compare current time against the stored last-seen timestamp.
    Updates the stored timestamp on success.
    Raises ClockTamperError if the clock went back more than ROLLBACK_THRESHOLD_S.
    Never raises any other exception — I/O errors are logged and skipped.
    """
    now = _now if _now is not None else time.time()

    # Read existing guard
    if guard_file.exists():
        try:
            raw = guard_file.read_bytes()
            data = json.loads(raw)
            stored_ts: float = float(data["ts"])
            stored_sig: bytes = bytes.fromhex(data["sig"])

            if not _verify(stored_ts, stored_sig, license_id):
                # Guard file was tampered with — treat as rollback evidence
                log.error("Clock guard file signature invalid. Treating as tamper.")
                raise ClockTamperError(
                    "License clock guard file was modified. Contact DrishtiAI."
                )

            rollback = stored_ts - now
            if rollback > ROLLBACK_THRESHOLD_S:
                raise ClockTamperError(
                    f"System clock moved backward by {rollback:.0f}s. "
                    "Verify your system time is correct, then contact DrishtiAI."
                )
        except ClockTamperError:
            raise
        except Exception as exc:
            # Corrupted or unreadable guard — log and overwrite (safe fail-open for I/O)
            log.warning("Could not read clock guard file (%s): %s. Re-anchoring.", guard_file, exc)

    # Write new guard
    try:
        guard_file.parent.mkdir(parents=True, exist_ok=True)
        sig = _sign(now, license_id)
        guard_file.write_bytes(
            json.dumps({"ts": now, "sig": sig.hex()}).encode()
        )
    except OSError as exc:
        log.warning("Cannot write clock guard file (%s): %s. Skipping.", guard_file, exc)
