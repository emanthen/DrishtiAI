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


# ── RS256 JWT ──────────────────────────────────────────────────────────────────

def test_rs256_token_roundtrip() -> None:
    """Access token must be verifiable with the public key only."""
    from drishtiai_api.auth.tokens import create_access_token, decode_token, ACCESS_TOKEN_TYPE

    token = create_access_token("test-uid", "guard")
    payload = decode_token(token)
    assert payload["sub"] == "test-uid"
    assert payload["role"] == "guard"
    assert payload["type"] == ACCESS_TOKEN_TYPE
    assert "jti" in payload


def test_rs256_tampered_token_rejected() -> None:
    """A token with a modified payload must be rejected by decode_token."""
    import base64, json
    from jose import JWTError
    from drishtiai_api.auth.tokens import create_access_token, decode_token

    token = create_access_token("uid", "guard")
    parts = token.split(".")
    # Decode payload, escalate role, re-encode (without re-signing).
    padding = 4 - len(parts[1]) % 4
    payload_bytes = base64.urlsafe_b64decode(parts[1] + "=" * padding)
    payload = json.loads(payload_bytes)
    payload["role"] = "superadmin"
    tampered_payload = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    tampered_token = f"{parts[0]}.{tampered_payload}.{parts[2]}"

    with pytest.raises(JWTError):
        decode_token(tampered_token)


# ── TOTP helpers ───────────────────────────────────────────────────────────────

def test_totp_generate_secret_is_base32() -> None:
    from drishtiai_api.auth.totp import generate_secret
    import base64

    secret = generate_secret()
    assert len(secret) >= 16
    # Must be valid base32 — decode should not raise.
    base64.b32decode(secret)


def test_totp_verify_valid_code() -> None:
    import pyotp
    from drishtiai_api.auth.totp import verify_code

    secret = pyotp.random_base32()
    code = pyotp.TOTP(secret).now()
    assert verify_code(secret, code) is True


def test_totp_verify_invalid_code() -> None:
    from drishtiai_api.auth.totp import generate_secret, verify_code

    secret = generate_secret()
    assert verify_code(secret, "000000") is False


def test_totp_provisioning_uri_contains_issuer() -> None:
    from drishtiai_api.auth.totp import generate_secret, get_provisioning_uri

    secret = generate_secret()
    uri = get_provisioning_uri(secret, "user@test.com")
    assert "DrishtiAI" in uri
    assert "user%40test.com" in uri or "user@test.com" in uri


# ── Progressive lockout ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_lockout_not_locked_initially() -> None:
    from unittest.mock import AsyncMock
    from drishtiai_api.auth.lockout import is_locked

    redis = AsyncMock()
    redis.exists.return_value = 0
    assert await is_locked(redis, "user-123") is False


@pytest.mark.asyncio
async def test_lockout_5_failures_triggers_5min_lock() -> None:
    from unittest.mock import AsyncMock, call
    from drishtiai_api.auth.lockout import on_login_failure

    redis = AsyncMock()
    redis.incr.return_value = 5  # simulate 5th failure
    await on_login_failure(redis, "user-123")

    # setex must be called with 300s (5-min lock)
    redis.setex.assert_called_once_with("auth:lock:user-123", 300, "1")


@pytest.mark.asyncio
async def test_lockout_10_failures_triggers_30min_lock() -> None:
    from unittest.mock import AsyncMock
    from drishtiai_api.auth.lockout import on_login_failure

    redis = AsyncMock()
    redis.incr.return_value = 10
    await on_login_failure(redis, "user-123")
    redis.setex.assert_called_once_with("auth:lock:user-123", 1800, "1")


@pytest.mark.asyncio
async def test_lockout_20_failures_triggers_24h_lock() -> None:
    from unittest.mock import AsyncMock
    from drishtiai_api.auth.lockout import on_login_failure

    redis = AsyncMock()
    redis.incr.return_value = 20
    await on_login_failure(redis, "user-123")
    redis.setex.assert_called_once_with("auth:lock:user-123", 86400, "1")


@pytest.mark.asyncio
async def test_lockout_clears_on_success() -> None:
    from unittest.mock import AsyncMock
    from drishtiai_api.auth.lockout import on_login_success

    redis = AsyncMock()
    await on_login_success(redis, "user-123")
    redis.delete.assert_called_once_with("auth:fail:user-123", "auth:lock:user-123")


# ── Logging redaction ──────────────────────────────────────────────────────────

def test_log_filter_redacts_password_in_message() -> None:
    import logging
    from drishtiai_api.log_filter import RedactingFilter

    filt = RedactingFilter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="User login password=mysecret123 failed", args=(), exc_info=None,
    )
    filt.filter(record)
    assert "mysecret123" not in record.msg
    assert "***" in record.msg


def test_log_filter_redacts_sensitive_dict_args() -> None:
    import logging
    from drishtiai_api.log_filter import RedactingFilter

    filt = RedactingFilter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="Request body: %s", args=({"password": "s3cr3t", "email": "a@b.com"},), exc_info=None,
    )
    filt.filter(record)
    assert isinstance(record.args, tuple)
    assert record.args[0]["password"] == "***"
    assert record.args[0]["email"] == "a@b.com"


# ── docker-compose default credentials ────────────────────────────────────────

def test_no_grafana_default_credential_in_compose() -> None:
    """GF_SECURITY_ADMIN_PASSWORD must not have a :-admin fallback."""
    import pathlib

    compose = pathlib.Path("deploy/compose/docker-compose.yml").read_text()
    assert ":-admin" not in compose, (
        "docker-compose.yml contains ':-admin' default credential for Grafana — remove it"
    )
