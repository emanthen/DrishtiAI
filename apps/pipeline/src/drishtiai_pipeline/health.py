"""
Health reporter: updates camera.health_status in Postgres periodically,
and publishes camera metadata (fps, frame count) to Redis.
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
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def record_frame(self) -> None:
        with self._lock:
            self._frame_count += 1
            self._last_frame_ts = time.monotonic()

    def _loop(self) -> None:
        while True:
            time.sleep(self._interval)
            try:
                with self._lock:
                    count = self._frame_count
                    last = self._last_frame_ts
                now = time.monotonic()
                elapsed = now - last if last > 0 else self._interval
                is_alive = elapsed < self._interval * 2

                status = HealthStatus.online if is_alive else HealthStatus.offline
                camera = self._db.get(Camera, self._camera_id)
                if camera and camera.health_status != status:
                    camera.health_status = status
                    self._db.commit()
                    logger.info("Camera %s health → %s", self._camera_id, status.value)

                meta = json.dumps({
                    "camera_id": str(self._camera_id),
                    "status": status.value,
                    "frames_processed": count,
                    "ts": time.time(),
                })
                self._redis.publish(f"camera:{self._camera_id}:meta", meta)
            except Exception:
                logger.exception("Health reporter error for camera %s", self._camera_id)
