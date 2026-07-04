"""
Audit log query endpoint.

Only superadmin and site_admin can read audit logs.
site_admin sees only entries where the actor belongs to their sites.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, and_

from drishtiai_shared.models.audit import AuditLog
from ..deps import CurrentUser, DbSession

router = APIRouter()


class AuditLogOut(BaseModel):
    id: uuid.UUID
    actor_user_id: uuid.UUID | None
    action: str
    target_type: str | None
    target_id: str | None
    ts: datetime
    ip: str | None
    meta_json: dict[str, Any] | None

    model_config = {"from_attributes": True}


class AuditPage(BaseModel):
    items: list[AuditLogOut]
    next_cursor: str | None


@router.get("", response_model=AuditPage)
async def list_audit_logs(
    current_user: CurrentUser,
    db: DbSession,
    action: Annotated[str | None, Query(description="Filter by action prefix, e.g. 'user.login'")] = None,
    actor_user_id: Annotated[uuid.UUID | None, Query()] = None,
    target_type: Annotated[str | None, Query()] = None,
    target_id: Annotated[str | None, Query()] = None,
    from_ts: Annotated[datetime | None, Query(alias="from")] = None,
    to_ts: Annotated[datetime | None, Query(alias="to")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    cursor: Annotated[str | None, Query()] = None,
) -> AuditPage:
    from drishtiai_shared.models.user import UserRole
    if current_user.role not in (UserRole.superadmin, UserRole.site_admin, UserRole.auditor):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")

    filters = []
    if action:
        filters.append(AuditLog.action.startswith(action))
    if actor_user_id:
        filters.append(AuditLog.actor_user_id == actor_user_id)
    if target_type:
        filters.append(AuditLog.target_type == target_type)
    if target_id:
        filters.append(AuditLog.target_id == target_id)
    if from_ts:
        filters.append(AuditLog.ts >= from_ts)
    if to_ts:
        filters.append(AuditLog.ts <= to_ts)
    if cursor:
        try:
            filters.append(AuditLog.ts < datetime.fromisoformat(cursor))
        except ValueError:
            pass

    q = (
        select(AuditLog)
        .where(and_(*filters) if filters else True)
        .order_by(AuditLog.ts.desc())
        .limit(limit + 1)
    )
    rows = list(db.scalars(q).all())

    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = rows[-1].ts.isoformat()

    return AuditPage(items=rows, next_cursor=next_cursor)  # type: ignore[arg-type]
