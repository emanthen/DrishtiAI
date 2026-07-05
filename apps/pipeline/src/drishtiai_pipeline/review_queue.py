"""
Write low-confidence plate reads to review_queue for human correction.

Reads between pipeline_min_confidence and pipeline_ocr_confidence_threshold
land here instead of being silently discarded.  Guards review and correct them
via the web UI; corrections are written to ml/plate-ocr/corrections/ to serve
as training data for the next fine-tuned OCR model.
"""
import io
import logging
import uuid
from datetime import datetime, timezone

import cv2
from minio import Minio
from sqlalchemy.orm import Session

from drishtiai_shared.models.review_queue import ReviewQueueItem, ReviewQueueStatus
from drishtiai_pipeline.ocr import PlateDetection

logger = logging.getLogger(__name__)


def write_review_item(
    *,
    detection: PlateDetection,
    camera_id: uuid.UUID,
    site_id: uuid.UUID,
    db: Session,
    minio_client: Minio,
    snapshot_bucket: str,
) -> ReviewQueueItem:
    ts = datetime.now(tz=timezone.utc)

    snapshot_key: str | None = None
    if detection.crop is not None and detection.crop.size > 0:
        try:
            _, buf = cv2.imencode(".jpg", detection.crop, [cv2.IMWRITE_JPEG_QUALITY, 90])
            jpeg_bytes = buf.tobytes()
            snapshot_key = f"review/{ts.strftime('%Y/%m/%d')}/{uuid.uuid4()}.jpg"
            minio_client.put_object(
                snapshot_bucket,
                snapshot_key,
                io.BytesIO(jpeg_bytes),
                len(jpeg_bytes),
                content_type="image/jpeg",
            )
        except Exception:
            logger.exception("Failed to upload review snapshot for plate %s", detection.text)

    item = ReviewQueueItem(
        id=uuid.uuid4(),
        site_id=site_id,
        camera_id=camera_id,
        ts=ts,
        snapshot_key=snapshot_key,
        raw_text=detection.text,
        raw_confidence=detection.confidence,
        status=ReviewQueueStatus.pending,
    )
    db.add(item)
    db.commit()

    logger.info(
        "Low-confidence read queued: %s (conf=%.2f)", detection.text, detection.confidence
    )
    return item
