"""
Health reporter: updates camera.health_status in Postgres periodically,
publishes live metadata to Redis pub/sub, and maintains a short-TTL
heartbeat key so the API can check real-time status without subscribing.

Redis keys:
  camera:heartbeat:{id}  — JSON blob, TTL 30 s; absence → offline
  drishti:system:camera_events pub/sub — status-change events
"""
import json
import logging
import threading
import time
import uuid

import redis
from sqlalchemy.orm import Session

from drishtiai_shared.models.camera import Camera, HealthStatus

logger = logging.getLogger(__name__)

_HEARTBEAT_TTL = 30  # seconds; 3× the default report_interval


class CameraHealthReporter:
    def __init__(
        self,
        camera_id: uuid.UUID,
        db: Session,
        redis_client: redis.Redis,
        report_interval: float = 10.0,
    ) -> None:
        self._camera_id = camera_id
        self._db = db
        self._redis = redis_client
        self._interval = report_interval
        self._frame_count = 0
        self._last_frame_ts: float = 0.0
        self._lock = threading.Lock()
        self._prev_status: HealthStatus | None = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def record_frame(self) -> None:
        with self._lock:
            self._frame_count += 1
            self._last_frame_ts = time.monotonic()

    def mark_offline(self) -> None:
        """Call on clean shutdown so the key doesn't linger until TTL expiry."""
        try:
            self._redis.delete(f"camera:heartbeat:{self._camera_id}")
            self._publish_status_change(HealthStatus.offline, fps=0.0)
            camera = self._db.get(Camera, self._camera_id)
            if camera and camera.health_status != HealthStatus.offline:
                camera.health_status = HealthStatus.offline
                self._db.commit()
        except Exception:
            logger.exception("mark_offline error for camera %s", self._camera_id)

    def stop(self) -> None:
        self._stop.set()

    def _publish_status_change(self, status: HealthStatus, fps: float) -> None:
        payload = json.dumps({
            "camera_id": str(self._camera_id),
            "status": status.value,
            "fps": round(fps, 1),
            "ts": time.time(),
        })
        self._redis.publish("drishti:system:camera_events", payload)

    def _loop(self) -> None:
        prev_count = 0
        prev_ts = time.monotonic()

        while not self._stop.is_set():
            time.sleep(self._interval)
            try:
                with self._lock:
                    count = self._frame_count
                    last = self._last_frame_ts

                now = time.monotonic()
                elapsed = now - last if last > 0 else self._interval
                is_alive = elapsed < self._interval * 2

                # Approximate fps over the last interval
                interval_elapsed = now - prev_ts
                fps = (count - prev_count) / interval_elapsed if interval_elapsed > 0 else 0.0
                prev_count = count
                prev_ts = now

                status = HealthStatus.online if is_alive else HealthStatus.offline

                # Heartbeat key — TTL=30 s; API reads this for real-time status
                heartbeat = json.dumps({
                    "camera_id": str(self._camera_id),
                    "status": status.value,
                    "fps": round(fps, 1),
                    "frames": count,
                    "ts": time.time(),
                })
                if is_alive:
                    self._redis.setex(
                        f"camera:heartbeat:{self._camera_id}",
                        _HEARTBEAT_TTL,
                        heartbeat,
                    )
                else:
                    self._redis.delete(f"camera:heartbeat:{self._camera_id}")

                # DB update on status change only
                camera = self._db.get(Camera, self._camera_id)
                if camera and camera.health_status != status:
                    camera.health_status = status
                    self._db.commit()
                    logger.info("Camera %s health → %s", self._camera_id, status.value)

                # Pub/sub — always (for live dashboard); status-change event to system channel
                meta = json.dumps({
                    "camera_id": str(self._camera_id),
                    "status": status.value,
                    "fps": round(fps, 1),
                    "frames_processed": count,
                    "ts": time.time(),
                })
                self._redis.publish(f"camera:{self._camera_id}:meta", meta)

                if status != self._prev_status and self._prev_status is not None:
                    self._publish_status_change(status, fps)
                self._prev_status = status

            except Exception:
                logger.exception("Health reporter error for camera %s", self._camera_id)
