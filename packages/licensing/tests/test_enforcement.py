"""
Tests for the enforcement module — specifically the gate safety properties.

Per the build spec: "The enforcement path must be covered by tests that
specifically assert the gate's physical safe-fallback on every non-valid state."
"""
from __future__ import annotations

import pytest

import drishtiai_licensing.enforcement as enf
from drishtiai_licensing.verifier import LicenseState


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset module-level state before each test."""
    enf.set_state(LicenseState.INVALID, None, "test reset")
    yield
    enf.set_state(LicenseState.INVALID, None, "test teardown")


# ── Gate automation safety ────────────────────────────────────────────────────

class TestGateSafety:
    """Gate automation must stop — not lock — on any non-operational state."""

    def test_gate_allowed_when_valid(self, base_claims):
        enf.set_state(LicenseState.VALID, base_claims)
        assert enf.gate_automation_allowed() is True

    def test_gate_allowed_when_warning(self, base_claims):
        enf.set_state(LicenseState.WARNING, base_claims)
        assert enf.gate_automation_allowed() is True

    def test_gate_allowed_when_grace(self, base_claims):
        enf.set_state(LicenseState.GRACE, base_claims)
        assert enf.gate_automation_allowed() is True

    def test_gate_blocked_when_expired(self, base_claims):
        enf.set_state(LicenseState.EXPIRED, base_claims)
        assert enf.gate_automation_allowed() is False

    def test_gate_blocked_when_hardware_mismatch(self, base_claims):
        enf.set_state(LicenseState.HARDWARE_MISMATCH, base_claims)
        assert enf.gate_automation_allowed() is False

    def test_gate_blocked_when_invalid(self):
        enf.set_state(LicenseState.INVALID, None)
        assert enf.gate_automation_allowed() is False


# ── Feature flags ─────────────────────────────────────────────────────────────

class TestFeatureFlags:
    def test_anpr_allowed_when_valid(self, base_claims):
        enf.set_state(LicenseState.VALID, base_claims)
        assert enf.is_feature_allowed("anpr") is True

    def test_anpr_blocked_when_expired(self, base_claims):
        enf.set_state(LicenseState.EXPIRED, base_claims)
        assert enf.is_feature_allowed("anpr") is False

    def test_live_view_always_allowed(self):
        """live_view is in ALWAYS_ALLOWED — must work even on INVALID."""
        for state in LicenseState:
            enf.set_state(state, None)
            assert enf.is_feature_allowed("live_view") is True, (
                f"live_view must be allowed in state {state}"
            )

    def test_audit_log_always_allowed(self):
        for state in LicenseState:
            enf.set_state(state, None)
            assert enf.is_feature_allowed("audit_log_read") is True

    def test_gate_manual_always_allowed(self):
        for state in LicenseState:
            enf.set_state(state, None)
            assert enf.is_feature_allowed("gate_manual") is True


# ── Camera limit ──────────────────────────────────────────────────────────────

class TestCameraLimit:
    def test_camera_limit_from_claims(self, base_claims):
        enf.set_state(LicenseState.VALID, base_claims)
        assert enf.camera_limit() == base_claims.camera_limit

    def test_camera_limit_zero_when_no_claims(self):
        enf.set_state(LicenseState.INVALID, None)
        assert enf.camera_limit() == 0


# ── Expiry banner ─────────────────────────────────────────────────────────────

class TestExpiryBanner:
    def test_no_banner_when_valid(self, base_claims):
        enf.set_state(LicenseState.VALID, base_claims)
        assert enf.expiry_banner() is None

    def test_warn_banner_when_warning(self, base_claims):
        enf.set_state(LicenseState.WARNING, base_claims, "Expires in 10 days")
        banner = enf.expiry_banner()
        assert banner is not None
        assert banner["level"] == "warn"

    def test_error_banner_when_expired(self, base_claims):
        enf.set_state(LicenseState.EXPIRED, base_claims, "License expired")
        banner = enf.expiry_banner()
        assert banner is not None
        assert banner["level"] == "error"

    def test_error_banner_when_invalid(self):
        enf.set_state(LicenseState.INVALID, None, "No license")
        banner = enf.expiry_banner()
        assert banner is not None
        assert banner["level"] == "error"
        assert banner["days_remaining"] is None


# ── Non-valid states: complete coverage ───────────────────────────────────────

class TestNonOperationalCoverage:
    """Every non-VALID state must block gate automation."""
    NON_OPERATIONAL = [
        LicenseState.EXPIRED,
        LicenseState.HARDWARE_MISMATCH,
        LicenseState.INVALID,
    ]

    def test_all_non_operational_block_gate(self):
        for state in self.NON_OPERATIONAL:
            enf.set_state(state, None)
            assert enf.gate_automation_allowed() is False, (
                f"gate_automation_allowed() must be False in state {state.value}"
            )
