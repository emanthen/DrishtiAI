from datetime import timedelta

from fastapi import HTTPException, status
from minio import Minio
from minio.error import S3Error

from drishtiai_api.config import settings

_client: Minio | None = None


def get_minio() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
    return _client


def _safe_minio_key(key: str) -> str:
    """Reject keys with path traversal sequences or absolute paths."""
    if ".." in key or key.startswith("/") or "\\" in key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid object key",
        )
    return key


async def get_presigned_url(
    bucket: str,
    key: str,
    expires_seconds: int | None = None,
) -> str:
    key = _safe_minio_key(key)
    ttl = expires_seconds if expires_seconds is not None else settings.minio_presigned_ttl_seconds
    client = get_minio()
    try:
        url = client.presigned_get_object(bucket, key, expires=timedelta(seconds=ttl))
    except S3Error as e:
        raise FileNotFoundError(f"Object not found: {key}") from e
    return url
