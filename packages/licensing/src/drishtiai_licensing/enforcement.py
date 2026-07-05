"""
License enforcement — module-level singleton that the pipeline and API read.

Set by calling initialize() at startup. gate_automation_allowed() and
is_feature_allowed() are the two call sites used throughout the product.

Gate safety principle: on any non-operational state this module does NOT send
a "close" or "lock" command. It simply stops calling evaluate_and_trigger().
The barrier hardware then follows its own physical default (manual button,
relay override). DrishtiAI can only open gates; it cannot hold them closed.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from drishtiai_licensing.clock_guard import ClockTamperError, check_and_update
from drishtiai_licensing.token import LicenseClaims
from drishtiai_licensing.verifier import LicenseState, evaluate_state

log = logging.getLogger(__name__)

# ── Module-level singleton ────────────────────────────────────────────────────
_state: LicenseState = LicenseState.INVALID
_claims: LicenseClaims | None = None
_message: str = "License not yet evaluated."

# States where the product operates normally (full or near-full features)
_OPERATIONAL = frozenset({LicenseState.VALID, LicenseState.WARNING, LicenseState.GRACE})

# Features always permitted regardless of license state (safety + compliance)
ALWAYS_ALLOWED = frozenset({"live_view", "gate_manual", "audit_log_read"})

# Default token path; overridden by LICENSE_TOKEN_PATH env var
DEFAULT_TOKEN_PATH = Path(os.getenv("LICENSE_TOKEN_PATH", "/etc/drishtiai/license.token"))
DEFAULT_GUARD_FILE = Path(os.getenv("LICENSE_GUARD_FILE", "/var/lib/drishtiai/.clockguard"))


def initialize(
    token_path: str | Path | None = None,
    guard_file: str | Path | None = None,
) -> tuple[LicenseState, str]:
    """
    Evaluate the license at startup. Call once from API lifespan and pipeline main.
    Returns (state, message) — always succeeds, never raises.
    """
    global _state, _claims, _message

    tpath = Path(token_path) if token_path else DEFAULT_TOKEN_PATH
    gfile = Path(guard_file) if guard_file else DEFAULT_GUARD_FILE

    state, claims, message = evaluate_state(tpath)

    # Clock-rollback check (only if we have valid claims to derive key from)
    if claims is not None:
        try:
            check_and_update(gfile, claims.license_id)
        except ClockTamperError as exc:
            log.error("Clock tamper detected: %s", exc)
            state = LicenseState.INVALID
            message = f"Clock rollback detected. {exc}"
            claims = None

    _state = state
    _claims = claims
    _message = message

    log.info("License state: %s — %s", state.value, message)
    return state, message


def set_state(state: LicenseState, claims: LicenseClaims | None, message: str = "") -> None:
    """Override state directly (used in tests and by the periodic re-check)."""
    global _state, _claims, _message
    _state = state
    _claims = claims
    _message = message or state.value


def get_state() -> LicenseState:
    return _state


def get_claims() -> LicenseClaims | None:
    return _claims


def get_message() -> str:
    return _message


def gate_automation_allowed() -> bool:
    """
    Returns True if the pipeline may evaluate GateRules and trigger controllers.
    False in EXPIRED / HARDWARE_MISMATCH / INVALID — hardware then governs the barrier.
    """
    return _state in _OPERATIONAL


def is_feature_allowed(feature: str) -> bool:
    """Return True if the feature may be used under the current license state."""
    if feature in ALWAYS_ALLOWED:
        return True
    return _state in _OPERATIONAL


def has_licensed_feature(feature: str) -> bool:
    """Return True if state permits AND the feature is in the license's feature list."""
    if not is_feature_allowed(feature):
        return False
    return _claims is not None and feature in _claims.features


def camera_limit() -> int:
    """Return the licensed camera limit, or 0 if no valid claims."""
    return _claims.camera_limit if _claims is not None else 0


def expiry_banner() -> dict | None:
    """
    Return banner data for the dashboard, or None if state is VALID.
    Shape: {level: "warn"|"error", message: str, days_remaining: int|None}
    """
    if _state == LicenseState.VALID:
        return None
    level = "warn" if _state in (LicenseState.WARNING, LicenseState.GRACE) else "error"
    days = _claims.days_until_expiry() if _claims else None
    return {"level": level, "message": _message, "days_remaining": days}
