"""
DrishtiAI pipeline — Phase 2: multi-camera, GStreamer capture + PaddleOCR +
multi-frame voter + alert engine.

Phase 3: Replace capture with DeepStream (nvcr.io/nvidia/deepstream).
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
from drishtiai_pipeline import gst_capture
from drishtiai_pipeline.capture import StreamCapture
from drishtiai_pipeline.config import settings
from drishtiai_pipeline.dedup import PlateDeduplicator
from drishtiai_pipeline.health import CameraHealthReporter
from drishtiai_pipeline.ocr import PlateDetection, detect_plates
from drishtiai_pipeline.voter import PlateVoter
from drishtiai_pipeline.writer import write_plate_event
from drishtiai_pipeline import alert_engine, gate, parking_session

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

    # Gate repeated emits of the same plate (e.g. looping test video)
    dedup = PlateDeduplicator(window_seconds=settings.pipeline_dedup_seconds)

    def _on_consensus(det: PlateDetection) -> None:
        if det.confidence < settings.pipeline_ocr_confidence_threshold:
            return
        if not dedup.is_new(det.text):
            return
        try:
            event = write_plate_event(
                detection=det,
                camera_id=camera_id,
                site_id=site_id,
                db=db,
                minio_client=minio,
                redis_client=r,
                snapshot_bucket=settings.minio_bucket_snapshots,
            )
            alert_engine.check_and_fire(
                db=db,
                redis_client=r,
                site_id=site_id,
                event_id=event.id,
                plate_text=det.text,
            )
            parking_session.on_plate_read(
                db=db,
                r=r,
                site_id=site_id,
                event_id=event.id,
                plate_text=det.text,
                camera_role=camera.role,
            )
            gate.evaluate_and_trigger(
                db=db,
                site_id=site_id,
                camera_id=camera_id,
                event_id=event.id,
                plate_text=det.text,
            )
        except Exception:
            logger.exception("Failed to write plate event for %s", det.text)

    voter = PlateVoter(
        on_plate=_on_consensus,
        window_s=settings.pipeline_voter_window_s,
        exit_gap_s=settings.pipeline_voter_exit_gap_s,
        min_reads=settings.pipeline_voter_min_reads,
    )

    health = CameraHealthReporter(camera_id, db, r)

    # Prefer GStreamer; fall back to OpenCV if unavailable
    capture = gst_capture.make_capture(
        stream_url=camera.stream_url,
        camera_id=str(camera_id),
        frame_sample=settings.pipeline_frame_sample,
        fallback_cls=StreamCapture,
    )

    mjpeg_counter = 0
    try:
        for frame_bgr, ts in capture.frames():
            if _shutdown.is_set():
                break

            health.record_frame()

            mjpeg_counter += 1
            if mjpeg_counter % settings.pipeline_mjpeg_every_n == 0:
                try:
                    _, jpeg_buf = cv2.imencode(".jpg", frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 70])
                    r.publish(f"camera:{camera_id}:frames", jpeg_buf.tobytes())
                except Exception:
                    pass

            detections = detect_plates(frame_bgr)
            voter.update(detections, ts)

    finally:
        health.stop()
        health.mark_offline()
        voter.flush()
        capture.release()
        db.close()
        r.close()
        logger.info("Pipeline stopped for camera %s", camera_id)


def main() -> None:
    logger.info(
        "DrishtiAI pipeline starting (Phase 2 — GStreamer/OpenCV + PaddleOCR + voter + alert engine)"
    )

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

    threads = []
    for camera in cameras:
        if not camera.stream_url:
            logger.warning("Camera %s has no stream URL — skipping", camera.name)
            continue
        t = threading.Thread(
            target=process_camera,
            args=(camera,),
            name=f"cam-{camera.id}",
            daemon=True,
        )
        t.start()
        threads.append(t)

    _shutdown.wait()

    for t in threads:
        t.join(timeout=10)

    logger.info("Pipeline shutdown complete.")


if __name__ == "__main__":
    main()
