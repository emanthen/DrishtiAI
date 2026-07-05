"""
System health — real probes for all subsystems.
GET /system/health — returns per-component status and overall ok flag.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select, text

from drishtiai_shared.models.retention import DataClass, RetentionPolicy
from drishtiai_shared.models.user import UserRole
from drishtiai_api.deps import CurrentUser, DbSession, RedisClient, require_role
from drishtiai_api.partition_manager import drop_old_partitions, ensure_partitions, list_partitions
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
    partitions: ComponentStatus


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

    # ── Event partitions ──────────────────────────────────────────────────────
    try:
        parts = list_partitions(db)
        today = date.today()
        current_name = f"events_{today.year}_{today.month:02d}"
        has_current = any(p["name"] == current_name for p in parts)
        if not has_current:
            results["partitions"] = ComponentStatus(
                status="error",
                detail=f"Missing partition for current month ({current_name})",
            )
        else:
            results["partitions"] = ComponentStatus(status="ok", detail=f"{len(parts)} partition(s)")
    except Exception as exc:
        results["partitions"] = ComponentStatus(status="error", detail=str(exc))

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


# ── DB stats ──────────────────────────────────────────────────────────────────

class PartitionInfo(BaseModel):
    name: str
    bounds: str
    row_estimate: int


class DbStats(BaseModel):
    partitions: list[PartitionInfo]
    total_event_estimate: int


@router.get("/db-stats", response_model=DbStats)
async def db_stats(current_user: CurrentUser, db: DbSession) -> DbStats:
    """Partition list with row estimates from pg_class."""
    parts = list_partitions(db)
    return DbStats(
        partitions=[PartitionInfo(**p) for p in parts],
        total_event_estimate=sum(p["row_estimate"] for p in parts),
    )


# ── Drop old partitions ────────────────────────────────────────────────────────

class DropResult(BaseModel):
    dropped: list[str]


@router.post(
    "/drop-old-partitions",
    response_model=DropResult,
    dependencies=[require_role(UserRole.superadmin, UserRole.site_admin)],
)
async def drop_old_partitions_endpoint(
    current_user: CurrentUser,
    db: DbSession,
    older_than_months: Annotated[int, Query(ge=1, le=120)] = 12,
) -> DropResult:
    """Drop monthly event partitions older than N months. site_admin+ only."""
    dropped = drop_old_partitions(db, older_than_months)
    return DropResult(dropped=dropped)


# ── Retention policies ────────────────────────────────────────────────────────

class RetentionPolicyOut(BaseModel):
    id: uuid.UUID
    site_id: uuid.UUID
    data_class: str
    retain_days: int

    model_config = {"from_attributes": True}


class RetentionPolicyIn(BaseModel):
    site_id: uuid.UUID
    data_class: DataClass
    retain_days: int


@router.get("/retention-policies", response_model=list[RetentionPolicyOut])
async def list_retention_policies(
    current_user: CurrentUser,
    db: DbSession,
    site_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[RetentionPolicy]:
    q = select(RetentionPolicy)
    if site_id:
        q = q.where(RetentionPolicy.site_id == site_id)
    return list(db.scalars(q).all())


@router.put("/retention-policies", response_model=RetentionPolicyOut)
async def upsert_retention_policy(
    body: RetentionPolicyIn,
    current_user: CurrentUser,
    db: DbSession,
) -> RetentionPolicy:
    existing = db.scalar(
        select(RetentionPolicy)
        .where(RetentionPolicy.site_id == body.site_id)
        .where(RetentionPolicy.data_class == body.data_class.value)
    )
    if existing:
        existing.retain_days = body.retain_days
        db.commit()
        db.refresh(existing)
        return existing
    policy = RetentionPolicy(
        id=uuid.uuid4(),
        site_id=body.site_id,
        data_class=body.data_class.value,
        retain_days=body.retain_days,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy
