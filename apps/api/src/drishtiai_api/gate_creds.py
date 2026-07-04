"""Fernet-based encrypt/decrypt/redact for gate controller credential fields."""
from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

_SENSITIVE = frozenset({"password", "secret"})


def _fernet(key: str) -> Fernet:
    return Fernet(key.encode() if not isinstance(key, bytes) else key)


def encrypt_config(config: dict, key: str) -> dict:
    """Encrypt sensitive string fields in a gate config dict."""
    if not key or not config:
        return config
    f = _fernet(key)
    return {
        k: f.encrypt(v.encode()).decode() if k in _SENSITIVE and isinstance(v, str) else v
        for k, v in config.items()
    }


def decrypt_config(config: dict, key: str) -> dict:
    """Decrypt sensitive fields. Falls back to plaintext for legacy unencrypted rows."""
    if not key or not config:
        return config
    f = _fernet(key)
    result = {}
    for k, v in config.items():
        if k in _SENSITIVE and isinstance(v, str) and v:
            try:
                result[k] = f.decrypt(v.encode()).decode()
            except (InvalidToken, Exception):
                result[k] = v  # plaintext legacy row — passes through
        else:
            result[k] = v
    return result


def redact_config(config: dict) -> dict:
    """Return config with sensitive fields replaced by '***' for API responses."""
    return {k: "***" if k in _SENSITIVE else v for k, v in config.items()}
