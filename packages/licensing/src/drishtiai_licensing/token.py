"""
License token — sign (server-side, private key) and verify (client-side, public key).

Token format (compact, no JWT dependency):
    1.<base64url(canonical_json)>.<base64url(ed25519_signature)>

The signature covers exactly the string "1.<base64url(canonical_json)>".
Editing any field in the payload — including expires_at, camera_limit, features —
changes the base64url encoding and invalidates the signature.

sign()  : requires the Ed25519 private key. Only called from cli.py / license server.
verify(): uses the baked-in public key. Called in the product at startup and on timer.
"""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_pem_public_key

from drishtiai_licensing.fingerprint import FingerprintBundle

_PUBLIC_KEY_PATH = Path(__file__).parent / "keys" / "public_key.pem"
TOKEN_VERSION = 1


class PlanTier(str, Enum):
    smb = "smb"
    mid = "mid"
    enterprise = "enterprise"


class InvalidLicenseError(Exception):
    pass


@dataclass
class LicenseClaims:
    license_id: str
    client_name: str
    site_id: str
    fingerprint: FingerprintBundle
    plan_tier: PlanTier
    camera_limit: int
    features: list[str]
    issued_at: datetime
    expires_at: datetime
    grace_days: int
    warning_days: int
    issuer: str = "DrishtiAI"
    token_version: int = TOKEN_VERSION

    def days_until_expiry(self, now: datetime | None = None) -> int:
        _now = now or datetime.now(tz=timezone.utc)
        if _now.tzinfo is None:
            _now = _now.replace(tzinfo=timezone.utc)
        return int((self.expires_at - _now).total_seconds() / 86400)

    def is_in_grace(self, now: datetime | None = None) -> bool:
        _now = now or datetime.now(tz=timezone.utc)
        if _now.tzinfo is None:
            _now = _now.replace(tzinfo=timezone.utc)
        return self.expires_at < _now <= self.expires_at + timedelta(days=self.grace_days)

    def has_expired_past_grace(self, now: datetime | None = None) -> bool:
        _now = now or datetime.now(tz=timezone.utc)
        if _now.tzinfo is None:
            _now = _now.replace(tzinfo=timezone.utc)
        return _now > self.expires_at + timedelta(days=self.grace_days)


# ── Encoding helpers ──────────────────────────────────────────────────────────

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    pad = 4 - len(s) % 4
    if pad != 4:
        s += "=" * pad
    return base64.urlsafe_b64decode(s)


def _to_canonical_json(claims: LicenseClaims) -> bytes:
    d: dict[str, Any] = {
        "license_id":   claims.license_id,
        "client_name":  claims.client_name,
        "site_id":      claims.site_id,
        "fingerprint":  claims.fingerprint.as_dict(),
        "plan_tier":    claims.plan_tier.value,
        "camera_limit": claims.camera_limit,
        "features":     sorted(claims.features),
        "issued_at":    claims.issued_at.isoformat(),
        "expires_at":   claims.expires_at.isoformat(),
        "grace_days":   claims.grace_days,
        "warning_days": claims.warning_days,
        "issuer":       claims.issuer,
        "token_version": claims.token_version,
    }
    return json.dumps(d, sort_keys=True, separators=(",", ":")).encode()


def _from_json(raw: bytes) -> LicenseClaims:
    d = json.loads(raw)
    return LicenseClaims(
        license_id=d["license_id"],
        client_name=d["client_name"],
        site_id=d["site_id"],
        fingerprint=FingerprintBundle.from_dict(d["fingerprint"]),
        plan_tier=PlanTier(d["plan_tier"]),
        camera_limit=int(d["camera_limit"]),
        features=list(d["features"]),
        issued_at=datetime.fromisoformat(d["issued_at"]),
        expires_at=datetime.fromisoformat(d["expires_at"]),
        grace_days=int(d["grace_days"]),
        warning_days=int(d["warning_days"]),
        issuer=d.get("issuer", "DrishtiAI"),
        token_version=int(d.get("token_version", TOKEN_VERSION)),
    )


# ── Public API ────────────────────────────────────────────────────────────────

def sign(claims: LicenseClaims, private_key_path: str | Path) -> str:
    """
    Sign claims with the Ed25519 private key.
    Only called from cli.py / the license server — never from the product install.
    """
    pem = Path(private_key_path).read_bytes()
    private_key: Ed25519PrivateKey = load_pem_private_key(pem, password=None)  # type: ignore[assignment]
    payload_b64 = _b64url_encode(_to_canonical_json(claims))
    signed_data = f"{TOKEN_VERSION}.{payload_b64}".encode()
    sig = private_key.sign(signed_data)
    return f"{TOKEN_VERSION}.{payload_b64}.{_b64url_encode(sig)}"


def verify(token_str: str, public_key_path: str | Path | None = None) -> LicenseClaims:
    """
    Verify the Ed25519 signature and return parsed claims.
    Uses the baked-in public key unless public_key_path is given (for tests).
    Raises InvalidLicenseError on any failure — never raises other exceptions.
    """
    try:
        parts = token_str.strip().split(".")
        if len(parts) != 3:
            raise InvalidLicenseError("Malformed token: expected 3 dot-separated parts")
        version, payload_b64, sig_b64 = parts
        if int(version) != TOKEN_VERSION:
            raise InvalidLicenseError(f"Unsupported token version: {version}")

        key_path = Path(public_key_path) if public_key_path else _PUBLIC_KEY_PATH
        pem = key_path.read_bytes()
        public_key: Ed25519PublicKey = load_pem_public_key(pem)  # type: ignore[assignment]

        signed_data = f"{version}.{payload_b64}".encode()
        public_key.verify(_b64url_decode(sig_b64), signed_data)

        return _from_json(_b64url_decode(payload_b64))

    except InvalidSignature:
        raise InvalidLicenseError("Token signature invalid — token may have been tampered with")
    except (KeyError, ValueError, json.JSONDecodeError, OSError) as exc:
        raise InvalidLicenseError(f"License verification failed: {exc}") from exc
    except InvalidLicenseError:
        raise
