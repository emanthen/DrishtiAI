"""Test configuration — runs before any test module is imported.

Sets JWT_PRIVATE_KEY_PEM / JWT_PUBLIC_KEY_PEM env vars so the Settings
singleton gets valid RSA keys when it's instantiated during test collection.
"""
import os

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# Generate a 2048-bit test keypair once per process.
_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

os.environ.setdefault(
    "JWT_PRIVATE_KEY_PEM",
    _key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode(),
)
os.environ.setdefault(
    "JWT_PUBLIC_KEY_PEM",
    _key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode(),
)
