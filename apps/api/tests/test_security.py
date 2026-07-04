"""
Security regression tests for PR 2 (auth-hardening).
Each test is labelled with the finding it guards.
"""
from __future__ import annotations

import socket
import uuid
from unittest.mock import MagicMock, patch

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from drishtiai_api.main import app


# ── H-05  Argon2id parameters ──────────────────────────────────────────────────

def test_argon2id_parameters() -> None:
    """Password hasher must use the approved Argon2id parameter set."""
    from drishtiai_api.auth.password import _ph

    assert _ph.time_cost == 3
    assert _ph.memory_cost == 65536
    assert _ph.parallelism == 4
    assert _ph.hash_len == 32
    assert _ph.salt_len == 16


def test_password_verify_correct() -> None:
    from drishtiai_api.auth.password import hash_password, verify_password

    h = hash_password("correct-horse-battery")
    assert verify_password("correct-horse-battery", h) is True


def test_password_verify_wrong() -> None:
    from drishtiai_api.auth.password import hash_password, verify_password

    h = hash_password("real-password")
    assert verify_password("wrong-password", h) is False


def test_dummy_hash_never_verifies() -> None:
    """DUMMY_HASH must not match any real input — timing-equalisation only."""
    from drishtiai_api.auth.password import DUMMY_HASH, verify_password

    assert verify_password("__dummy_password_never_valid__", DUMMY_HASH) is False
    assert verify_password("anything", DUMMY_HASH) is False


# ── H-01  Login error body uniformity ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_unknown_user_returns_401() -> None:
    """Unknown user → 401 Invalid credentials (no account-enumeration leak)."""
    with patch("drishtiai_api.routers.auth.get_db"):
        db = MagicMock()
        db.scalar.return_value = None   # user not found
        db.commit.return_value = None
        with patch("drishtiai_api.deps.get_db", return_value=iter([db])):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/auth/login",
                    json={"email": "nobody@example.com", "password": "whatever"},
                )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid credentials"


@pytest.mark.asyncio
async def test_login_disabled_account_same_body_as_wrong_password() -> None:
    """Disabled account and wrong password must return identical 401 bodies."""
    fake_user = MagicMock()
    fake_user.is_active = False
    fake_user.password_hash = "$argon2id$invalid"
    fake_user.id = uuid.uuid4()

    db = MagicMock()
    db.scalar.return_value = fake_user
    db.commit.return_value = None

    with patch("drishtiai_api.deps.get_db", return_value=iter([db])):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp_disabled = await client.post(
                "/auth/login",
                json={"email": "disabled@example.com", "password": "pw"},
            )

    db2 = MagicMock()
    db2.scalar.return_value = None
    db2.commit.return_value = None

    with patch("drishtiai_api.deps.get_db", return_value=iter([db2])):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp_unknown = await client.post(
                "/auth/login",
                json={"email": "nobody@example.com", "password": "pw"},
            )

    assert resp_disabled.status_code == resp_unknown.status_code == 401
    assert resp_disabled.json()["detail"] == resp_unknown.json()["detail"]


# ── H-04  SSRF guard ───────────────────────────────────────────────────────────

def test_ssrf_blocks_loopback() -> None:
    from drishtiai_api.http_safe import assert_public_url

    with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("127.0.0.1", 0))]):
        with pytest.raises(HTTPException) as exc_info:
            assert_public_url("http://internal.example.com/hook")
    assert exc_info.value.status_code == 400


def test_ssrf_blocks_rfc1918() -> None:
    from drishtiai_api.http_safe import assert_public_url

    with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("10.0.0.1", 0))]):
        with pytest.raises(HTTPException) as exc_info:
            assert_public_url("http://internal.corp/hook")
    assert exc_info.value.status_code == 400


def test_ssrf_blocks_link_local() -> None:
    from drishtiai_api.http_safe import assert_public_url

    with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("169.254.0.1", 0))]):
        with pytest.raises(HTTPException) as exc_info:
            assert_public_url("http://metadata.local/hook")
    assert exc_info.value.status_code == 400


def test_ssrf_blocks_non_http_scheme() -> None:
    from drishtiai_api.http_safe import assert_public_url

    with pytest.raises(HTTPException) as exc_info:
        assert_public_url("ftp://example.com/hook")
    assert exc_info.value.status_code == 400


def test_ssrf_allows_public_ip() -> None:
    from drishtiai_api.http_safe import assert_public_url

    with patch("socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 0))]):
        assert_public_url("https://example.com/webhook")  # must not raise


# ── B-01  Camera route ordering ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_camera_live_status_not_shadowed_by_id_param() -> None:
    """GET /cameras/live-status must be routed to the literal handler, not /{camera_id}.

    Without auth the literal route returns 403; the path-param route would return
    422 (UUID parse failure) — so 403 here proves the literal route wins.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/cameras/live-status")
    assert resp.status_code == 403, (
        "Expected 403 from literal /live-status handler; "
        f"got {resp.status_code} — route ordering may be broken"
    )


@pytest.mark.asyncio
async def test_camera_health_summary_not_shadowed() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/cameras/health-summary")
    assert resp.status_code == 403


# ── H-08  Gate credential encryption ──────────────────────────────────────────

def test_gate_creds_encrypt_decrypt_roundtrip() -> None:
    from drishtiai_api.gate_creds import decrypt_config, encrypt_config

    key = Fernet.generate_key().decode()
    config = {"host": "cam.example.com", "username": "admin", "password": "s3cr3t!"}
    encrypted = encrypt_config(config, key)

    assert encrypted["password"] != "s3cr3t!"   # must be ciphertext
    assert encrypted["username"] == "admin"       # username not in SENSITIVE set

    decrypted = decrypt_config(encrypted, key)
    assert decrypted["password"] == "s3cr3t!"
    assert decrypted["username"] == "admin"


def test_gate_creds_redact_strips_sensitive_fields() -> None:
    from drishtiai_api.gate_creds import redact_config

    config = {"url": "http://gate.example.com", "secret": "tok3n", "timeout": 5}
    redacted = redact_config(config)

    assert redacted["secret"] == "***"
    assert redacted["url"] == "http://gate.example.com"
    assert redacted["timeout"] == 5


def test_gate_creds_legacy_plaintext_survives_decrypt() -> None:
    """Rows written before encryption was enabled must survive decrypt gracefully."""
    from drishtiai_api.gate_creds import decrypt_config

    key = Fernet.generate_key().decode()
    config = {"password": "old-plaintext"}  # was never encrypted
    result = decrypt_config(config, key)
    # Falls back to original value instead of raising
    assert result["password"] == "old-plaintext"


def test_gate_creds_no_key_is_passthrough() -> None:
    from drishtiai_api.gate_creds import decrypt_config, encrypt_config

    config = {"password": "pw", "host": "x"}
    assert encrypt_config(config, "") == config
    assert decrypt_config(config, "") == config
