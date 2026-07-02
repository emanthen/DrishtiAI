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

    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    cors_origins: list[str] = ["http://localhost:3000"]


settings = Settings()
