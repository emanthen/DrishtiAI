"""
Persist a plate detection to Postgres and MinIO, then publish to Redis.
"""
import io
import json
import logging
import uuid
from datetime import datetime, timezone

import cv2
import numpy as np
import redis
from minio import Minio
from sqlalchemy.orm import Session

from drishtiai_shared.models.event import Event, EventKind
from drishtiai_shared.models.plate import Plate, PlateFormat
from drishtiai_pipeline.ocr import PlateDetection

logger = logging.getLogger(__name__)


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def write_plate_event(
    *,
    detection: PlateDetection,
    camera_id: uuid.UUID,
    site_id: uuid.UUID,
    db: Session,
    minio_client: Minio,
    redis_client: redis.Redis,
    snapshot_bucket: str,
) -> Event:
    ts = _now_utc()

    # 1. Upsert Plate record
    from sqlalchemy import select
    existing_plate = db.scalar(select(Plate).where(Plate.text == detection.text))
    if existing_plate is None:
        plate = Plate(
            id=uuid.uuid4(),
            text=detection.text,
            region=None,
            format_class=PlateFormat.embossed,
        )
        db.add(plate)
        db.flush()
    else:
        plate = existing_plate

    # 2. Upload snapshot to MinIO
    snapshot_key: str | None = None
    if detection.crop is not None and detection.crop.size > 0:
        try:
            _, buf = cv2.imencode(".jpg", detection.crop, [cv2.IMWRITE_JPEG_QUALITY, 90])
            jpeg_bytes = buf.tobytes()
            snapshot_key = f"plates/{ts.strftime('%Y/%m/%d')}/{uuid.uuid4()}.jpg"
            minio_client.put_object(
                snapshot_bucket,
                snapshot_key,
                io.BytesIO(jpeg_bytes),
                length=len(jpeg_bytes),
                content_type="image/jpeg",
            )
        except Exception:
            logger.exception("Failed to upload snapshot for plate %s", detection.text)
            snapshot_key = None

    # 3. Write Event to Postgres
    event = Event(
        id=uuid.uuid4(),
        site_id=site_id,
        camera_id=camera_id,
        ts=ts,
        kind=EventKind.plate_read,
        plate_id=plate.id,
        snapshot_key=snapshot_key,
        confidence=detection.confidence,
        meta_json={"raw_text": detection.text},
    )
    db.add(event)
    db.commit()

    # 4. Publish to Redis
    try:
        payload = json.dumps({
            "event_id": str(event.id),
            "site_id": str(site_id),
            "camera_id": str(camera_id),
            "kind": "plate_read",
            "ts": ts.isoformat(),
            "plate": detection.text,
            "confidence": detection.confidence,
            "snapshot_key": snapshot_key,
        })
        redis_client.publish(f"drishti:{site_id}:events", payload)
    except Exception:
        logger.exception("Failed to publish event to Redis")

    logger.info("Plate read: %s (conf=%.2f) on camera %s", detection.text, detection.confidence, camera_id)
    return event
