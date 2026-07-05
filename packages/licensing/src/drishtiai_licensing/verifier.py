"""
License state machine — evaluated at startup and on a daily timer.

States (ordered by severity):
    VALID            — full function, no nags
    WARNING          — expiring within warning_days, full function + banner
    GRACE            — expired but within grace_days, full function + prominent warning
    EXPIRED          — past grace period, smart features suspended
    HARDWARE_MISMATCH— fingerprint quorum fails, smart features suspended
    INVALID          — bad signature / no file / clock tamper, smart features suspended
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from drishtiai_licensing.fingerprint import FingerprintBundle, generate_fingerprint, matches
from drishtiai_licensing.token import InvalidLicenseError, LicenseClaims, verify

log = logging.getLogger(__name__)


class LicenseState(str, Enum):
    VALID             = "valid"
    WARNING           = "warning"
    GRACE             = "grace"
    EXPIRED           = "expired"
    HARDWARE_MISMATCH = "hardware_mismatch"
    INVALID           = "invalid"


def evaluate_state(
    token_path: str | Path,
    *,
    now: datetime | None = None,
    _hw_override: FingerprintBundle | None = None,  # injectable for tests
) -> tuple[LicenseState, LicenseClaims | None, str]:
    """
    Read and evaluate the license token at token_path.
    Returns (state, claims_or_None, human_readable_message).
    Never raises — all failure modes return INVALID.
    """
    now = now or datetime.now(tz=timezone.utc)
    token_file = Path(token_path)

    if not token_file.exists():
        log.warning("License token not found: %s", token_file)
        return LicenseState.INVALID, None, _msg_invalid()

    try:
        token_str = token_file.read_text().strip()
        claims = verify(token_str)
    except InvalidLicenseError as exc:
        log.warning("License token invalid: %s", exc)
        return LicenseState.INVALID, None, _msg_invalid()
    except OSError as exc:
        log.warning("Cannot read license token: %s", exc)
        return LicenseState.INVALID, None, _msg_invalid()

    # Hardware quorum check
    hw = _hw_override or generate_fingerprint()
    if not matches(claims.fingerprint, hw):
        log.warning("License hardware mismatch. Licensed fingerprint does not match this machine.")
        return (
            LicenseState.HARDWARE_MISMATCH, claims,
            "License not valid for this hardware. Contact DrishtiAI.",
        )

    # Time-based state
    if claims.has_expired_past_grace(now):
        return (
            LicenseState.EXPIRED, claims,
            "License expired. Smart features suspended. Contact DrishtiAI to renew.",
        )

    if claims.is_in_grace(now):
        from datetime import timedelta
        grace_end = claims.expires_at + timedelta(days=claims.grace_days)
        days_left = max(0, int((grace_end - now).total_seconds() / 86400))
        return (
            LicenseState.GRACE, claims,
            f"License expired. {days_left} day(s) remaining in grace period. Renew immediately.",
        )

    days_remaining = claims.days_until_expiry(now)
    if days_remaining <= claims.warning_days:
        return (
            LicenseState.WARNING, claims,
            f"License expires in {days_remaining} day(s). Contact DrishtiAI to renew.",
        )

    return LicenseState.VALID, claims, "License valid."


def _msg_invalid() -> str:
    return "No valid license. Contact DrishtiAI."
