"""
GStreamer-based capture backend for DrishtiAI pipeline.

Replaces OpenCV VideoCapture with a proper GStreamer pipeline:
  rtspsrc → rtph264depay → h264parse → avdec_h264 → videoconvert → appsink

Advantages over OpenCV:
  - Native RTSP reconnection via rtspsrc retry-on-eos
  - Proper H.264 Annex-B parsing (no green-frame artefacts on reconnect)
  - Ready for DeepStream swap in Phase 3 (replace avdec_h264 with nvv4l2decoder)
  - One GLib main loop handles all streams via bus messages

Falls back to OpenCV StreamCapture if GStreamer Python bindings are not
installed (dev environments, CI without gstreamer packages).
"""
from __future__ import annotations

import logging
import queue
import time
import threading
from typing import Generator, Type

import numpy as np

log = logging.getLogger(__name__)

_GST_AVAILABLE = False
try:
    import gi
    gi.require_version("Gst", "1.0")
    from gi.repository import Gst, GLib  # type: ignore[import]
    Gst.init(None)
    _GST_AVAILABLE = True
except Exception:
    pass


class GstCapture:
    """
    GStreamer appsink capture — yields (frame_bgr_ndarray, timestamp_float) tuples.

    Parameters match `StreamCapture` so they are interchangeable.
    """

    _PIPELINE_TEMPLATE = (
        "rtspsrc location={url} latency=200 protocols=tcp "
        "retry=10 timeout=5000000 "
        "! rtph264depay ! h264parse ! avdec_h264 "
        "! videoconvert ! video/x-raw,format=BGR "
        "! appsink name=sink emit-signals=false max-buffers=2 drop=true sync=false"
    )

    def __init__(
        self,
        stream_url: str,
        camera_id: str = "",
        frame_sample: int = 5,
    ) -> None:
        if not _GST_AVAILABLE:
            raise RuntimeError("GStreamer Python bindings not available")

        self._url = stream_url
        self._camera_id = camera_id
        self._frame_sample = max(1, frame_sample)
        self._q: queue.Queue[tuple[np.ndarray, float]] = queue.Queue(maxsize=4)
        self._stop = threading.Event()
        self._pipeline: Gst.Pipeline | None = None
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _build_pipeline(self) -> Gst.Pipeline:
        desc = self._PIPELINE_TEMPLATE.format(url=self._url)
        pipeline = Gst.parse_launch(desc)
        return pipeline

    def _run(self) -> None:
        frame_count = 0
        consecutive_errors = 0

        while not self._stop.is_set():
            pipeline = self._build_pipeline()
            sink = pipeline.get_by_name("sink")
            pipeline.set_state(Gst.State.PLAYING)

            log.info("GStreamer pipeline started for camera %s", self._camera_id)
            try:
                while not self._stop.is_set():
                    sample = sink.try_pull_sample(Gst.SECOND)
                    if sample is None:
                        # Check bus for EOS/error
                        bus = pipeline.get_bus()
                        msg = bus.pop_filtered(
                            Gst.MessageType.EOS | Gst.MessageType.ERROR
                        )
                        if msg:
                            log.warning(
                                "GStreamer bus message for camera %s: %s",
                                self._camera_id,
                                msg.type,
                            )
                            break
                        continue

                    frame_count += 1
                    if frame_count % self._frame_sample != 0:
                        continue

                    buf = sample.get_buffer()
                    caps = sample.get_caps()
                    s = caps.get_structure(0)
                    w = s.get_value("width")
                    h = s.get_value("height")
                    ok, map_info = buf.map(Gst.MapFlags.READ)
                    if not ok:
                        continue
                    try:
                        arr = np.frombuffer(map_info.data, dtype=np.uint8)
                        frame = arr.reshape((h, w, 3)).copy()
                    finally:
                        buf.unmap(map_info)

                    ts = time.monotonic()
                    try:
                        self._q.put_nowait((frame, ts))
                    except queue.Full:
                        pass  # drop oldest; appsink's drop=true already handles backpressure

                    consecutive_errors = 0

            except Exception:
                log.exception("GStreamer capture error for camera %s", self._camera_id)
                consecutive_errors += 1
            finally:
                pipeline.set_state(Gst.State.NULL)

            if not self._stop.is_set():
                delay = min(5 * consecutive_errors, 30)
                log.info(
                    "Reconnecting camera %s in %ds (attempt %d)",
                    self._camera_id,
                    delay,
                    consecutive_errors,
                )
                time.sleep(delay)

    def frames(self) -> Generator[tuple[np.ndarray, float], None, None]:
        while not self._stop.is_set():
            try:
                frame, ts = self._q.get(timeout=2.0)
                yield frame, ts
            except queue.Empty:
                continue

    def release(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)


def make_capture(
    *,
    stream_url: str,
    camera_id: str,
    frame_sample: int,
    fallback_cls: Type,
) -> GstCapture:
    """
    Return a GstCapture if GStreamer is available, else fall back to fallback_cls.

    fallback_cls must accept (stream_url, camera_id, frame_sample) kwargs and
    expose a .frames() generator and .release() method (i.e. StreamCapture).
    """
    if _GST_AVAILABLE:
        log.info("Using GStreamer capture backend for camera %s", camera_id)
        return GstCapture(
            stream_url=stream_url,
            camera_id=camera_id,
            frame_sample=frame_sample,
        )
    else:
        log.warning(
            "GStreamer not available — falling back to OpenCV for camera %s", camera_id
        )
        return fallback_cls(
            stream_url=stream_url,
            camera_id=camera_id,
            frame_sample=frame_sample,
        )
