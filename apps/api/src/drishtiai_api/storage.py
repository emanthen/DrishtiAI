from datetime import timedelta

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


async def get_presigned_url(bucket: str, key: str, expires_seconds: int = 3600) -> str:
    client = get_minio()
    try:
        url = client.presigned_get_object(bucket, key, expires=timedelta(seconds=expires_seconds))
    except S3Error as e:
        raise FileNotFoundError(f"Object not found: {key}") from e
    return url
