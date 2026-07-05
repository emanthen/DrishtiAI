"""Tests for token sign / verify."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from drishtiai_licensing.token import (
    InvalidLicenseError,
    LicenseClaims,
    PlanTier,
    sign,
    verify,
)


class TestRoundtrip:
    def test_sign_verify_roundtrip(self, base_claims, keypair_dir):
        token = sign(base_claims, keypair_dir / "private_key.pem")
        claims = verify(token, keypair_dir / "public_key.pem")
        assert claims.license_id == base_claims.license_id
        assert claims.camera_limit == base_claims.camera_limit
        assert sorted(claims.features) == sorted(base_claims.features)

    def test_token_format(self, base_claims, keypair_dir):
        token = sign(base_claims, keypair_dir / "private_key.pem")
        parts = token.split(".")
        assert len(parts) == 3
        assert parts[0] == "1"

    def test_verify_uses_baked_in_key(self, base_claims, keypair_dir, monkeypatch):
        """verify() with no public_key_path falls back to the module's baked-in key."""
        from drishtiai_licensing import token as token_mod
        monkeypatch.setattr(token_mod, "_PUBLIC_KEY_PATH", keypair_dir / "public_key.pem")
        t = sign(base_claims, keypair_dir / "private_key.pem")
        claims = verify(t)
        assert claims.license_id == base_claims.license_id


class TestTamperDetection:
    def test_tampered_payload_rejected(self, base_claims, keypair_dir):
        token = sign(base_claims, keypair_dir / "private_key.pem")
        v, payload_b64, sig = token.split(".")
        # Flip one char in the middle of the payload
        mid = len(payload_b64) // 2
        flipped = payload_b64[:mid] + ("A" if payload_b64[mid] != "A" else "B") + payload_b64[mid + 1:]
        tampered = f"{v}.{flipped}.{sig}"
        with pytest.raises(InvalidLicenseError):
            verify(tampered, keypair_dir / "public_key.pem")

    def test_tampered_signature_rejected(self, base_claims, keypair_dir):
        token = sign(base_claims, keypair_dir / "private_key.pem")
        v, payload_b64, sig = token.split(".")
        bad_sig = sig[:-4] + "AAAA"
        tampered = f"{v}.{payload_b64}.{bad_sig}"
        with pytest.raises(InvalidLicenseError):
            verify(tampered, keypair_dir / "public_key.pem")

    def test_wrong_public_key_rejected(self, base_claims, keypair_dir, tmp_path):
        # Generate a second test keypair and verify that it rejects the first key's token
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import (
            Encoding,
            NoEncryption,
            PublicFormat,
            PrivateFormat,
        )
        other_priv = Ed25519PrivateKey.generate()
        other_pub_pem = other_priv.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
        other_pub_path = tmp_path / "other_pub.pem"
        other_pub_path.write_bytes(other_pub_pem)
        token = sign(base_claims, keypair_dir / "private_key.pem")
        with pytest.raises(InvalidLicenseError):
            verify(token, other_pub_path)

    def test_malformed_token_rejected(self, keypair_dir):
        with pytest.raises(InvalidLicenseError):
            verify("not.a.valid.token.string", keypair_dir / "public_key.pem")

    def test_wrong_version_rejected(self, base_claims, keypair_dir):
        token = sign(base_claims, keypair_dir / "private_key.pem")
        v, payload_b64, sig = token.split(".")
        with pytest.raises(InvalidLicenseError):
            verify(f"9.{payload_b64}.{sig}", keypair_dir / "public_key.pem")


class TestClaimsHelpers:
    def test_days_until_expiry(self, base_claims):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        assert base_claims.days_until_expiry(now) == 365

    def test_is_in_grace(self, base_claims):
        just_expired = base_claims.expires_at + timedelta(days=1)
        assert base_claims.is_in_grace(just_expired)

    def test_not_in_grace_before_expiry(self, base_claims):
        still_valid = base_claims.expires_at - timedelta(days=1)
        assert not base_claims.is_in_grace(still_valid)

    def test_has_expired_past_grace(self, base_claims):
        way_past = base_claims.expires_at + timedelta(days=base_claims.grace_days + 1)
        assert base_claims.has_expired_past_grace(way_past)

    def test_not_expired_in_grace(self, base_claims):
        in_grace = base_claims.expires_at + timedelta(days=1)
        assert not base_claims.has_expired_past_grace(in_grace)
