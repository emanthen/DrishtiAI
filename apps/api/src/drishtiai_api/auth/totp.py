import pyotp


def generate_secret() -> str:
    return pyotp.random_base32()


def get_provisioning_uri(secret: str, email: str, issuer: str = "DrishtiAI") -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)


def verify_code(secret: str, code: str) -> bool:
    """Verify a 6-digit TOTP code. Accepts ±1 window (30s tolerance)."""
    return pyotp.TOTP(secret).verify(code, valid_window=1)
