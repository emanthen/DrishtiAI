"""RTSP/video capture using OpenCV VideoCapture."""
import logging
import time
from collections.abc import Iterator

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class StreamCapture:
    """
    Wraps an OpenCV VideoCapture and yields frames with basic health checking.

    Reconnects automatically on stream failure after RECONNECT_DELAY seconds.
    """

    RECONNECT_DELAY = 5.0

    def __init__(self, stream_url: str, camera_id: str, frame_sample: int = 5) -> None:
        self.stream_url = stream_url
        self.camera_id = camera_id
        self.frame_sample = frame_sample
        self._cap: cv2.VideoCapture | None = None

    def _open(self) -> bool:
        if self._cap and self._cap.isOpened():
            self._cap.release()
        logger.info("Opening stream %s (camera %s)", self.stream_url, self.camera_id)
        self._cap = cv2.VideoCapture(self.stream_url)
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
        ok = self._cap.isOpened()
        if not ok:
            logger.warning("Failed to open stream %s", self.stream_url)
        return ok

    def frames(self) -> Iterator[tuple[np.ndarray, float]]:
        """Yield (frame_bgr, timestamp) tuples indefinitely, reconnecting on failure."""
        frame_count = 0
        while True:
            if not self._open():
                time.sleep(self.RECONNECT_DELAY)
                continue

            consecutive_failures = 0
            while True:
                ret, frame = self._cap.read()  # type: ignore[union-attr]
                if not ret:
                    consecutive_failures += 1
                    if consecutive_failures >= 10:
                        logger.warning("Stream %s lost, reconnecting", self.stream_url)
                        break
                    time.sleep(0.05)
                    continue

                consecutive_failures = 0
                frame_count += 1
                if frame_count % self.frame_sample != 0:
                    continue

                yield frame, time.time()

    def release(self) -> None:
        if self._cap:
            self._cap.release()
