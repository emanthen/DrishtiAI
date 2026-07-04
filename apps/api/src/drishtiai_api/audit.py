"""
Audit log write helper.

Call `log_action()` before or after committing a write to append an
immutable row to `audit_logs`.  The function adds to the session but
does NOT commit — let the surrounding endpoint commit (or call
`db.commit()` explicitly when the operation itself has no writes).
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from drishtiai_shared.models.audit import AuditLog


def log_action(
    db: Session,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    ip: str | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    """
    Append an audit entry to the current DB session.

    action examples:
        user.login_success   user.login_failed
        user.logout
        user.create          user.update
        user.deactivate      user.activate
        user.reset_password
        webhook.create       webhook.delete
        watchlist.create     watchlist_entry.add   watchlist_entry.remove
    """
    entry = AuditLog(
        id=uuid.uuid4(),
        actor_user_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        ip=ip,
        meta_json=meta,
    )
    db.add(entry)
