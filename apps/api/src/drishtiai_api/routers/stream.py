"""
MJPEG proxy for live camera viewing — Phase 1.

The pipeline publishes JPEG frames to Redis channel `camera:{id}:frames`.
This endpoint reads from that channel and streams as MJPEG to the browser.

Phase 2: Replace with HLS segments for better scalability.
"""
import asyncio
import uuid

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from drishtiai_api.deps import RedisClient

router = APIRouter()

BOUNDARY = b"--drishtiai-frame"
CRLF = b"\r\n"


@router.get("/{camera_id}/mjpeg")
async def mjpeg_stream(camera_id: uuid.UUID, redis: RedisClient) -> StreamingResponse:
    async def frame_generator():
        pubsub = redis.pubsub()
        await pubsub.subscribe(f"camera:{camera_id}:frames")
        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=5.0)
                if message and message["type"] == "message":
                    jpeg_bytes = message["data"]
                    if isinstance(jpeg_bytes, str):
                        jpeg_bytes = jpeg_bytes.encode("latin-1")
                    yield (
                        BOUNDARY + CRLF
                        + b"Content-Type: image/jpeg" + CRLF
                        + f"Content-Length: {len(jpeg_bytes)}".encode() + CRLF
                        + CRLF
                        + jpeg_bytes
                        + CRLF
                    )
                else:
                    await asyncio.sleep(0.033)
        finally:
            await pubsub.unsubscribe(f"camera:{camera_id}:frames")
            await pubsub.aclose()

    return StreamingResponse(
        frame_generator(),
        media_type=f"multipart/x-mixed-replace; boundary=drishtiai-frame",
    )
