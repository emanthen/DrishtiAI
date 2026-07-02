"""
DrishtiAI pipeline — Phase 1: single-camera, OpenCV + PaddleOCR.

Phase 2: Replace with DeepStream multi-stream pipeline.
"""
import logging
import signal
import sys
import threading
import uuid

import cv2
import redis as redis_lib
from minio import Minio
from sqlalchemy import select

from drishtiai_shared.db import SessionLocal
from drishtiai_shared.models.camera import Camera
from drishtiai_pipeline.capture import StreamCapture
from drishtiai_pipeline.config import settings
from drishtiai_pipeline.dedup import PlateDeduplicator
from drishtiai_pipeline.health import CameraHealthReporter
from drishtiai_pipeline.ocr import detect_plates
from drishtiai_pipeline.writer import write_plate_event

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

_shutdown = threading.Event()


def _handle_signal(*_) -> None:
    logger.info("Shutdown signal received")
    _shutdown.set()


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


def process_camera(camera: Camera) -> None:
    """Process a single camera stream until _shutdown is set."""
    camera_id = camera.id
    site_id = camera.site_id

    logger.info("Starting pipeline for camera %s (%s)", camera.name, camera_id)

    r = redis_lib.from_url(settings.redis_url)
    minio = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )
    db = SessionLocal()

    dedup = PlateDeduplicator(window_seconds=settings.pipeline_dedup_seconds)
    health = CameraHealthReporter(camera_id, db, r)
    capture = StreamCapture(
        stream_url=camera.stream_url,
        camera_id=str(camera_id),
        frame_sample=settings.pipeline_frame_sample,
    )

    mjpeg_counter = 0
    try:
        for frame_bgr, ts in capture.frames():
            if _shutdown.is_set():
                break

            health.record_frame()

            # Publish MJPEG frame to Redis for live view
            mjpeg_counter += 1
            if mjpeg_counter % settings.pipeline_mjpeg_every_n == 0:
                try:
                    _, jpeg_buf = cv2.imencode(".jpg", frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 70])
                    r.publish(f"camera:{camera_id}:frames", jpeg_buf.tobytes())
                except Exception:
                    pass

            # Plate detection + OCR
            detections = detect_plates(frame_bgr)
            for det in detections:
                if det.confidence < settings.pipeline_ocr_confidence_threshold:
                    continue
                if not dedup.is_new(det.text):
                    continue
                try:
                    write_plate_event(
                        detection=det,
                        camera_id=camera_id,
                        site_id=site_id,
                        db=db,
                        minio_client=minio,
                        redis_client=r,
                        snapshot_bucket=settings.minio_bucket_snapshots,
                    )
                except Exception:
                    logger.exception("Failed to write plate event for %s", det.text)

    finally:
        capture.release()
        db.close()
        r.close()
        logger.info("Pipeline stopped for camera %s", camera_id)


def main() -> None:
    logger.info("DrishtiAI pipeline starting (Phase 1 — OpenCV + PaddleOCR)")

    db = SessionLocal()
    try:
        q = select(Camera).where(Camera.enabled == True)  # noqa: E712
        if settings.pipeline_camera_ids != "all":
            ids = [uuid.UUID(s.strip()) for s in settings.pipeline_camera_ids.split(",") if s.strip()]
            q = q.where(Camera.id.in_(ids))
        cameras = list(db.scalars(q).all())
    finally:
        db.close()

    if not cameras:
        logger.error("No enabled cameras found. Add cameras via the admin panel.")
        sys.exit(1)

    logger.info("Processing %d camera(s): %s", len(cameras), [c.name for c in cameras])

    # Phase 1: process cameras sequentially in threads (one thread per camera)
    # Phase 2: DeepStream handles all streams in a single pipeline
    threads = []
    for camera in cameras:
        if not camera.stream_url:
            logger.warning("Camera %s has no stream URL — skipping", camera.name)
            continue
        t = threading.Thread(target=process_camera, args=(camera,), name=f"cam-{camera.id}", daemon=True)
        t.start()
        threads.append(t)

    _shutdown.wait()

    for t in threads:
        t.join(timeout=10)

    logger.info("Pipeline shutdown complete.")


if __name__ == "__main__":
    main()
