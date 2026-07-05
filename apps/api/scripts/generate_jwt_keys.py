"""Generate a fresh RSA-2048 keypair for JWT RS256 signing.

Run once at install time:
    python apps/api/scripts/generate_jwt_keys.py

Then add the printed lines to your .env file.
"""
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

private_pem = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode()

public_pem = private_key.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
).decode()

# Collapse to single-line form for .env compatibility
private_oneline = private_pem.replace("\n", "\\n")
public_oneline = public_pem.replace("\n", "\\n")

print("# Add these lines to your .env file:")
print(f'JWT_PRIVATE_KEY_PEM="{private_oneline}"')
print(f'JWT_PUBLIC_KEY_PEM="{public_oneline}"')
