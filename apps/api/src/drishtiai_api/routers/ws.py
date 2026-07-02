"""
WebSocket endpoints for real-time event streaming.
"""
import asyncio
import json
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/events")
async def ws_events(websocket: WebSocket) -> None:
    """
    Stream all site events in real time.

    Client sends: {"auth": "<access_token>"}
    Server sends: event JSON objects as they arrive via Redis pub/sub.

    Phase 1: single site, no auth verification on WS (auth done at HTTP layer).
    Phase 2: verify JWT on WS handshake, filter by site.
    """
    import redis.asyncio as aioredis
    from drishtiai_api.config import settings

    await websocket.accept()
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.psubscribe("drishti:*:events")

    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message["type"] == "pmessage":
                await websocket.send_text(message["data"])
            else:
                await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.punsubscribe("drishti:*:events")
        await pubsub.aclose()
        await r.aclose()


@router.websocket("/cameras/{camera_id}")
async def ws_camera(websocket: WebSocket, camera_id: uuid.UUID) -> None:
    """Stream live pipeline metadata for a single camera."""
    import redis.asyncio as aioredis
    from drishtiai_api.config import settings

    await websocket.accept()
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    pubsub = r.pubsub()
    channel = f"camera:{camera_id}:meta"
    await pubsub.subscribe(channel)

    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message["type"] == "message":
                await websocket.send_text(message["data"])
            else:
                await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
        await r.aclose()
