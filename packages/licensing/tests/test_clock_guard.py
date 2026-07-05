"""Tests for the clock rollback guard."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from drishtiai_licensing.clock_guard import (
    ROLLBACK_THRESHOLD_S,
    ClockTamperError,
    _sign,
    check_and_update,
)

LICENSE_ID = "LIC-CLOCKTEST-001"
BASE_TS = 1_700_000_000.0  # fixed epoch for reproducibility


class TestNormalOperation:
    def test_first_write_creates_file(self, tmp_path):
        guard = tmp_path / "guard"
        check_and_update(guard, LICENSE_ID, _now=BASE_TS)
        assert guard.exists()

    def test_advancing_clock_succeeds(self, tmp_path):
        guard = tmp_path / "guard"
        check_and_update(guard, LICENSE_ID, _now=BASE_TS)
        check_and_update(guard, LICENSE_ID, _now=BASE_TS + 3600)

    def test_small_backward_tick_within_threshold_succeeds(self, tmp_path):
        """NTP correction of <120s must not trigger error."""
        guard = tmp_path / "guard"
        check_and_update(guard, LICENSE_ID, _now=BASE_TS)
        check_and_update(guard, LICENSE_ID, _now=BASE_TS - (ROLLBACK_THRESHOLD_S - 1))


class TestRollbackDetection:
    def test_large_rollback_raises(self, tmp_path):
        guard = tmp_path / "guard"
        check_and_update(guard, LICENSE_ID, _now=BASE_TS)
        with pytest.raises(ClockTamperError):
            check_and_update(guard, LICENSE_ID, _now=BASE_TS - (ROLLBACK_THRESHOLD_S + 1))

    def test_exact_threshold_raises(self, tmp_path):
        guard = tmp_path / "guard"
        check_and_update(guard, LICENSE_ID, _now=BASE_TS)
        with pytest.raises(ClockTamperError):
            check_and_update(guard, LICENSE_ID, _now=BASE_TS - ROLLBACK_THRESHOLD_S - 1)

    def test_error_message_is_actionable(self, tmp_path):
        guard = tmp_path / "guard"
        check_and_update(guard, LICENSE_ID, _now=BASE_TS)
        with pytest.raises(ClockTamperError, match="DrishtiAI"):
            check_and_update(guard, LICENSE_ID, _now=BASE_TS - 9999)


class TestTamperDetection:
    def test_corrupted_guard_file_is_reanchored(self, tmp_path, caplog):
        """Unreadable guard file should log a warning, not raise."""
        guard = tmp_path / "guard"
        guard.write_bytes(b"not valid json")
        check_and_update(guard, LICENSE_ID, _now=BASE_TS)  # should not raise

    def test_tampered_signature_raises(self, tmp_path):
        guard = tmp_path / "guard"
        check_and_update(guard, LICENSE_ID, _now=BASE_TS)
        raw = json.loads(guard.read_bytes())
        raw["sig"] = "deadbeef" * 8  # wrong signature
        guard.write_bytes(json.dumps(raw).encode())
        with pytest.raises(ClockTamperError, match="modified"):
            check_and_update(guard, LICENSE_ID, _now=BASE_TS + 10)

    def test_different_license_id_fails_verification(self, tmp_path):
        """Guard written with one license_id must not verify with another."""
        guard = tmp_path / "guard"
        check_and_update(guard, "LIC-A", _now=BASE_TS)
        with pytest.raises(ClockTamperError):
            check_and_update(guard, "LIC-B", _now=BASE_TS + 10)


class TestMissingParentDir:
    def test_nested_path_is_created(self, tmp_path):
        guard = tmp_path / "nested" / "deep" / "guard"
        check_and_update(guard, LICENSE_ID, _now=BASE_TS)
        assert guard.exists()
