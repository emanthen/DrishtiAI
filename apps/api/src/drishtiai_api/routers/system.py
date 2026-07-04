"""
System health — real probes for all subsystems.
GET /system/health — returns per-component status and overall ok flag.
"""
from __future__ import annotations

import asyncio
import os

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from drishtiai_api.deps import DbSession, RedisClient
from drishtiai_api.storage import get_minio

_WEAK_PASSWORDS = {"admin", "password", "grafana", "changeme", "123456", "drishtiai"}

router = APIRouter()


class ComponentStatus(BaseModel):
    status: str          # "ok" | "error"
    detail: str | None = None


class SystemHealth(BaseModel):
    ok: bool
    api: ComponentStatus
    database: ComponentStatus
    redis: ComponentStatus
    minio: ComponentStatus
    pipeline: ComponentStatus


@router.get("/health", response_model=SystemHealth)
async def system_health(db: DbSession, redis: RedisClient) -> SystemHealth:
    results: dict[str, ComponentStatus] = {}

    # ── Postgres ──────────────────────────────────────────────────────────────
    try:
        db.execute(text("SELECT 1"))
        results["database"] = ComponentStatus(status="ok")
    except Exception as exc:
        results["database"] = ComponentStatus(status="error", detail=str(exc))

    # ── Redis ─────────────────────────────────────────────────────────────────
    try:
        await redis.ping()
        results["redis"] = ComponentStatus(status="ok")
    except Exception as exc:
        results["redis"] = ComponentStatus(status="error", detail=str(exc))

    # ── MinIO ─────────────────────────────────────────────────────────────────
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, get_minio().list_buckets)
        results["minio"] = ComponentStatus(status="ok")
    except Exception as exc:
        results["minio"] = ComponentStatus(status="error", detail=str(exc))

    # ── Pipeline (via camera heartbeat keys) ──────────────────────────────────
    try:
        keys = await redis.keys("camera:heartbeat:*")
        if keys:
            results["pipeline"] = ComponentStatus(status="ok", detail=f"{len(keys)} camera(s) reporting")
        else:
            results["pipeline"] = ComponentStatus(status="ok", detail="no cameras online")
    except Exception as exc:
        results["pipeline"] = ComponentStatus(status="error", detail=str(exc))

    results["api"] = ComponentStatus(status="ok")

    # Warn on weak credentials — never fail health for this, just surface it
    weak = []
    if os.getenv("GRAFANA_PASSWORD", "") in _WEAK_PASSWORDS:
        weak.append("GRAFANA_PASSWORD")
    if os.getenv("MINIO_ROOT_PASSWORD", "") in _WEAK_PASSWORDS:
        weak.append("MINIO_ROOT_PASSWORD")
    if os.getenv("POSTGRES_PASSWORD", "") in _WEAK_PASSWORDS:
        weak.append("POSTGRES_PASSWORD")
    if weak:
        results["api"] = ComponentStatus(
            status="ok",
            detail=f"WEAK_CREDENTIAL: {', '.join(weak)} — change before go-live",
        )

    all_ok = all(c.status == "ok" for c in results.values())
    return SystemHealth(ok=all_ok, **results)
