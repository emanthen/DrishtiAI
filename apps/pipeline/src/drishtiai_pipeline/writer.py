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
from drishtiai_shared.models.vehicle import Vehicle
from drishtiai_pipeline.color_detect import detect_color
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

    # 1. Detect vehicle color from the body region above the plate (if available)
    vehicle_color = None
    vehicle_color_conf = 0.0
    if detection.vehicle_crop is not None and detection.vehicle_crop.size > 0:
        color_result = detect_color(detection.vehicle_crop)
        if color_result:
            vehicle_color, vehicle_color_conf = color_result

    # 2. Upsert Plate record
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

    # 3. Upsert Vehicle linked to this plate
    vehicle: Vehicle
    if plate.vehicle_id is not None:
        vehicle = db.get(Vehicle, plate.vehicle_id)  # type: ignore[assignment]
        vehicle.last_seen = ts
        # Update color only when the new observation is more confident
        if vehicle_color and vehicle_color_conf > (vehicle.color_confidence or 0.0):
            vehicle.color = vehicle_color.value
            vehicle.color_confidence = vehicle_color_conf
    else:
        vehicle = Vehicle(
            id=uuid.uuid4(),
            first_seen=ts,
            last_seen=ts,
            color=vehicle_color.value if vehicle_color else None,
            color_confidence=vehicle_color_conf if vehicle_color else None,
        )
        db.add(vehicle)
        db.flush()
        plate.vehicle_id = vehicle.id

    # 4. Upload snapshot to MinIO
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

    # 5. Write Event to Postgres
    event = Event(
        id=uuid.uuid4(),
        site_id=site_id,
        camera_id=camera_id,
        ts=ts,
        kind=EventKind.plate_read,
        vehicle_id=vehicle.id,
        plate_id=plate.id,
        snapshot_key=snapshot_key,
        confidence=detection.confidence,
        meta_json={"raw_text": detection.text},
    )
    db.add(event)
    db.commit()

    # 6. Publish to Redis
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
