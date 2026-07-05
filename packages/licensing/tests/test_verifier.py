"""Tests for the license state machine (verifier)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from drishtiai_licensing.token import sign
from drishtiai_licensing.verifier import LicenseState, evaluate_state


class TestValidState:
    def test_valid_returns_valid(self, token_file, test_fingerprint, monkeypatch):
        token_path, pub_path = token_file
        monkeypatch.setattr(
            "drishtiai_licensing.verifier.generate_fingerprint",
            lambda: test_fingerprint,
        )
        from drishtiai_licensing import verifier as v_mod
        monkeypatch.setattr(v_mod, "verify", lambda s: __import__(
            "drishtiai_licensing.token", fromlist=["verify"]
        ).verify(s, pub_path))
        now = datetime(2026, 2, 1, tzinfo=timezone.utc)
        state, claims, msg = evaluate_state(token_path, now=now, _hw_override=test_fingerprint)
        assert state == LicenseState.VALID
        assert claims is not None

    def test_missing_token_returns_invalid(self, tmp_path, test_fingerprint):
        state, claims, msg = evaluate_state(
            tmp_path / "missing.token", _hw_override=test_fingerprint
        )
        assert state == LicenseState.INVALID
        assert claims is None
        assert "contact" in msg.lower()

    def test_corrupted_token_returns_invalid(self, tmp_path, test_fingerprint):
        bad = tmp_path / "bad.token"
        bad.write_text("garbage.not.a.token")
        state, claims, msg = evaluate_state(bad, _hw_override=test_fingerprint)
        assert state == LicenseState.INVALID


class TestExpiryStates:
    def _make_token_file(
        self,
        base_claims,
        keypair_dir,
        tmp_path,
        delta_days: int,
        pub_key_monkeypatch=None,
    ):
        from drishtiai_licensing.token import LicenseClaims
        import dataclasses
        now_base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        claims = dataclasses.replace(
            base_claims,
            issued_at=now_base,
            expires_at=now_base + timedelta(days=delta_days),
        )
        token = sign(claims, keypair_dir / "private_key.pem")
        token_path = tmp_path / "license.token"
        token_path.write_text(token)
        return token_path

    def test_warning_state(self, base_claims, keypair_dir, tmp_path, test_fingerprint, monkeypatch):
        """15 days left when warning_days=30 → WARNING."""
        token_path = self._make_token_file(base_claims, keypair_dir, tmp_path, delta_days=15)
        from drishtiai_licensing import verifier as v_mod
        monkeypatch.setattr(v_mod, "verify", lambda s: __import__(
            "drishtiai_licensing.token", fromlist=["verify"]
        ).verify(s, keypair_dir / "public_key.pem"))
        # "now" is right after issue so 15 days remain
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        state, claims, msg = evaluate_state(token_path, now=now, _hw_override=test_fingerprint)
        assert state == LicenseState.WARNING
        assert "expire" in msg.lower()

    def test_grace_state(self, base_claims, keypair_dir, tmp_path, test_fingerprint, monkeypatch):
        """Token expired yesterday, still within 14-day grace."""
        token_path = self._make_token_file(base_claims, keypair_dir, tmp_path, delta_days=0)
        from drishtiai_licensing import verifier as v_mod
        monkeypatch.setattr(v_mod, "verify", lambda s: __import__(
            "drishtiai_licensing.token", fromlist=["verify"]
        ).verify(s, keypair_dir / "public_key.pem"))
        now = datetime(2026, 1, 2, tzinfo=timezone.utc)  # 1 day past issue = in grace
        state, claims, msg = evaluate_state(token_path, now=now, _hw_override=test_fingerprint)
        assert state == LicenseState.GRACE
        assert "grace" in msg.lower()

    def test_expired_state(self, base_claims, keypair_dir, tmp_path, test_fingerprint, monkeypatch):
        """Token expired 20 days ago, grace is 14 days → EXPIRED."""
        token_path = self._make_token_file(base_claims, keypair_dir, tmp_path, delta_days=0)
        from drishtiai_licensing import verifier as v_mod
        monkeypatch.setattr(v_mod, "verify", lambda s: __import__(
            "drishtiai_licensing.token", fromlist=["verify"]
        ).verify(s, keypair_dir / "public_key.pem"))
        now = datetime(2026, 1, 20, tzinfo=timezone.utc)  # 20 days past issue, grace=14
        state, claims, msg = evaluate_state(token_path, now=now, _hw_override=test_fingerprint)
        assert state == LicenseState.EXPIRED
        assert "renew" in msg.lower()


class TestHardwareMismatch:
    def test_hardware_mismatch_state(self, token_file, other_fingerprint, monkeypatch):
        token_path, pub_path = token_file
        from drishtiai_licensing import verifier as v_mod
        monkeypatch.setattr(v_mod, "verify", lambda s: __import__(
            "drishtiai_licensing.token", fromlist=["verify"]
        ).verify(s, pub_path))
        now = datetime(2026, 2, 1, tzinfo=timezone.utc)
        state, claims, msg = evaluate_state(
            token_path, now=now, _hw_override=other_fingerprint
        )
        assert state == LicenseState.HARDWARE_MISMATCH
        assert "hardware" in msg.lower()
        # claims are still returned so the operator knows whose license it is
        assert claims is not None
