"""Shared fixtures for licensing tests."""
from __future__ import annotations

import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from drishtiai_licensing.fingerprint import FingerprintBundle
from drishtiai_licensing.token import LicenseClaims, PlanTier, sign

# ── Test keypair ──────────────────────────────────────────────────────────────
# Generated offline with:
#   openssl genpkey -algorithm Ed25519 -out test_private.pem
#   openssl pkey -in test_private.pem -pubout -out test_public.pem
# These keys are for tests ONLY — never use them in production.

TEST_PRIVATE_PEM = b"""\
-----BEGIN PRIVATE KEY-----
MC4CAQAwBQYDK2VwBCIEICSpmNivFv+2k+48IAnhUxY/zkep+9/UvnexOZCEmjax
-----END PRIVATE KEY-----
"""

TEST_PUBLIC_PEM = b"""\
-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAJsezxff4zSksQwCTMStpmcaJBsf84YbuIYd1fS/SYKo=
-----END PUBLIC KEY-----
"""


@pytest.fixture()
def keypair_dir(tmp_path: Path) -> Path:
    """Write test keypair to a temp dir and return the dir path."""
    (tmp_path / "private_key.pem").write_bytes(TEST_PRIVATE_PEM)
    (tmp_path / "public_key.pem").write_bytes(TEST_PUBLIC_PEM)
    return tmp_path


@pytest.fixture()
def test_fingerprint() -> FingerprintBundle:
    return FingerprintBundle(
        motherboard="TESTBOARD001",
        cpu="TESTCPU001",
        disk="TESTDISK001",
        mac="TESTMAC0001",
    )


@pytest.fixture()
def other_fingerprint() -> FingerprintBundle:
    """Different hardware — only 1-of-4 match with test_fingerprint."""
    return FingerprintBundle(
        motherboard="OTHERBOARD99",
        cpu="OTHERCPU9999",
        disk="OTHERDISK999",
        mac="TESTMAC0001",  # only MAC matches
    )


@pytest.fixture()
def base_claims(test_fingerprint: FingerprintBundle) -> LicenseClaims:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return LicenseClaims(
        license_id="LIC-TEST-0001",
        client_name="Test Client",
        site_id="SITE-001",
        fingerprint=test_fingerprint,
        plan_tier=PlanTier.smb,
        camera_limit=4,
        features=["anpr", "gate_automation", "alerts"],
        issued_at=now,
        expires_at=now + timedelta(days=365),
        grace_days=14,
        warning_days=30,
    )


@pytest.fixture()
def valid_token(base_claims: LicenseClaims, keypair_dir: Path) -> tuple[str, Path]:
    """Returns (token_str, public_key_path)."""
    token = sign(base_claims, keypair_dir / "private_key.pem")
    return token, keypair_dir / "public_key.pem"


@pytest.fixture()
def token_file(valid_token: tuple[str, Path], tmp_path: Path) -> tuple[Path, Path]:
    """Writes the token to a file, returns (token_path, public_key_path)."""
    token_str, pub_path = valid_token
    token_path = tmp_path / "license.token"
    token_path.write_text(token_str)
    return token_path, pub_path
