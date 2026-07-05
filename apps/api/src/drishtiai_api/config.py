from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "DrishtiAI API"
    debug: bool = False
    secret_key: str = "change-me-in-production"

    database_url: str = "postgresql+psycopg://drishtiai:drishtiai@postgres:5432/drishtiai"
    redis_url: str = "redis://redis:6379/0"

    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "drishtiai"
    minio_secret_key: str = "change-me-in-production"
    minio_secure: bool = False
    minio_bucket_snapshots: str = "snapshots"
    minio_bucket_clips: str = "clips"

    # RS256 JWT keys — PEM-encoded strings.
    # Generate with: make keygen
    # In .env, use the single-line form output by generate_jwt_keys.py
    # (backslash-n literal in the value is normalised to real newlines below).
    jwt_private_key_pem: str = ""
    jwt_public_key_pem: str = ""

    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    cors_origins: list[str] = ["http://localhost:3000"]

    # MinIO presigned URL TTL — shorter for sensitive media
    minio_presigned_ttl_seconds: int = 900  # 15 minutes

    # Fernet key for encrypting ONVIF credentials at rest.
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # Leave empty in dev — credentials stored plaintext with a warning.
    gate_credential_key: str = ""

    @field_validator("jwt_private_key_pem", "jwt_public_key_pem", mode="before")
    @classmethod
    def _normalise_pem(cls, v: str) -> str:
        # Handle both quoted multi-line PEM and single-line with literal \n
        return v.replace("\\n", "\n") if isinstance(v, str) else v


settings = Settings()
