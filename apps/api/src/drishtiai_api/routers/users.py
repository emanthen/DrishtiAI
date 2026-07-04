"""
User management — Phase 9.

Role hierarchy for write operations:
  superadmin  → can create/edit any role
  site_admin  → can create/edit manager, guard, resident, auditor
                (not superadmin or another site_admin)
  manager     → read-only list of own site

All writers are scoped to the caller's org. site_admin is further
scoped to sites they belong to.
"""
import secrets
import string
import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from drishtiai_api.sanitize import strip_html
from drishtiai_api.schemas import RequestModel
from sqlalchemy import select

from drishtiai_shared.models.user import User, UserRole
from drishtiai_api.audit import log_action
from drishtiai_api.auth.password import hash_password
from drishtiai_api.deps import CurrentUser, DbSession, require_role

router = APIRouter()

# Roles a site_admin is allowed to assign
_SITE_ADMIN_ASSIGNABLE = {
    UserRole.manager,
    UserRole.guard,
    UserRole.resident,
    UserRole.auditor,
}


# ── Schemas ───────────────────────────────────────────────────────────────────

class UserOut(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    phone: str | None
    role: UserRole
    site_ids: list[str]
    is_active: bool
    created_at: str

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_user(cls, u: User) -> "UserOut":
        return cls(
            id=u.id,
            name=u.name,
            email=u.email,
            phone=u.phone,
            role=u.role,
            site_ids=u.site_ids or [],
            is_active=u.is_active,
            created_at=u.created_at.isoformat(),
        )


class UserCreate(RequestModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=30)
    role: UserRole
    site_ids: list[str] = Field(default_factory=list, max_length=50)
    password: str | None = Field(default=None, min_length=8, max_length=1024)

    @field_validator("name")
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        return strip_html(v).strip()


class UserPatch(RequestModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    role: UserRole | None = None
    site_ids: list[str] | None = Field(default=None, max_length=50)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def sanitize_name(cls, v: str | None) -> str | None:
        return strip_html(v).strip() if v is not None else v


class SetPasswordBody(RequestModel):
    password: str = Field(min_length=8, max_length=1024)


class SetPasswordResponse(BaseModel):
    password: str  # returned only when auto-generated


# ── Helpers ───────────────────────────────────────────────────────────────────

def _assert_can_manage_role(caller: User, target_role: UserRole) -> None:
    if caller.role == UserRole.superadmin:
        return
    if caller.role == UserRole.site_admin and target_role in _SITE_ADMIN_ASSIGNABLE:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Cannot assign role '{target_role.value}'")


def _assert_site_scope(caller: User, site_ids: list[str]) -> None:
    """site_admin may only assign sites they themselves belong to."""
    if caller.role == UserRole.superadmin:
        return
    caller_sites = set(caller.site_ids or [])
    bad = [s for s in site_ids if s not in caller_sites]
    if bad:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Not authorised for sites: {bad}")


def _gen_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return "".join(secrets.choice(alphabet) for _ in range(length))


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[UserOut])
async def list_users(
    current_user: CurrentUser,
    db: DbSession,
    role: Annotated[UserRole | None, Query()] = None,
    is_active: Annotated[bool | None, Query()] = None,
) -> list[UserOut]:
    if current_user.role not in (UserRole.superadmin, UserRole.site_admin, UserRole.manager):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    q = select(User).where(User.org_id == current_user.org_id)

    # site_admin / manager see only users who share at least one site
    if current_user.role in (UserRole.site_admin, UserRole.manager):
        caller_sites = current_user.site_ids or []
        if caller_sites:
            q = q.where(User.site_ids.overlap(caller_sites))  # type: ignore[attr-defined]

    if role is not None:
        q = q.where(User.role == role)
    if is_active is not None:
        q = q.where(User.is_active == is_active)

    q = q.order_by(User.name)
    users = db.scalars(q).all()
    return [UserOut.from_orm_user(u) for u in users]


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("", response_model=SetPasswordResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    current_user: CurrentUser,
    db: DbSession,
) -> SetPasswordResponse:
    if current_user.role not in (UserRole.superadmin, UserRole.site_admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    _assert_can_manage_role(current_user, body.role)
    _assert_site_scope(current_user, body.site_ids)

    existing = db.scalar(select(User).where(User.email == body.email))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    plain = body.password or _gen_password()
    user = User(
        id=uuid.uuid4(),
        org_id=current_user.org_id,
        name=body.name,
        email=body.email,
        phone=body.phone,
        role=body.role,
        site_ids=body.site_ids,
        password_hash=hash_password(plain),
        is_active=True,
    )
    db.add(user)
    log_action(db, actor_id=current_user.id, action="user.create",
               target_type="user", target_id=str(user.id),
               meta={"role": body.role.value, "email": body.email})
    db.commit()
    return SetPasswordResponse(password=plain)


# ── Get ───────────────────────────────────────────────────────────────────────

@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> UserOut:
    user = db.get(User, user_id)
    if user is None or user.org_id != current_user.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserOut.from_orm_user(user)


# ── Update ────────────────────────────────────────────────────────────────────

@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: uuid.UUID,
    body: UserPatch,
    current_user: CurrentUser,
    db: DbSession,
) -> UserOut:
    if current_user.role not in (UserRole.superadmin, UserRole.site_admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    user = db.get(User, user_id)
    if user is None or user.org_id != current_user.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if body.role is not None:
        _assert_can_manage_role(current_user, body.role)
    if body.site_ids is not None:
        _assert_site_scope(current_user, body.site_ids)

    if body.name is not None:
        user.name = body.name
    if body.email is not None:
        existing = db.scalar(select(User).where(User.email == body.email, User.id != user_id))
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")
        user.email = body.email
    if body.phone is not None:
        user.phone = body.phone
    if body.role is not None:
        user.role = body.role
    if body.site_ids is not None:
        user.site_ids = body.site_ids
    if body.is_active is not None:
        user.is_active = body.is_active

    action = "user.activate" if body.is_active else ("user.deactivate" if body.is_active is False else "user.update")
    log_action(db, actor_id=current_user.id, action=action,
               target_type="user", target_id=str(user_id))
    db.commit()
    db.refresh(user)
    return UserOut.from_orm_user(user)


# ── Deactivate ────────────────────────────────────────────────────────────────

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
    user_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> None:
    if current_user.role not in (UserRole.superadmin, UserRole.site_admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate yourself")

    user = db.get(User, user_id)
    if user is None or user.org_id != current_user.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_active = False
    log_action(db, actor_id=current_user.id, action="user.deactivate",
               target_type="user", target_id=str(user_id))
    db.commit()


# ── Reset password ────────────────────────────────────────────────────────────

@router.post("/{user_id}/set-password", response_model=SetPasswordResponse)
async def set_password(
    user_id: uuid.UUID,
    body: SetPasswordBody | None = None,
    *,
    current_user: CurrentUser,
    db: DbSession,
) -> SetPasswordResponse:
    if current_user.role not in (UserRole.superadmin, UserRole.site_admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    user = db.get(User, user_id)
    if user is None or user.org_id != current_user.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    plain = (body.password if body and body.password else None) or _gen_password()
    user.password_hash = hash_password(plain)
    log_action(db, actor_id=current_user.id, action="user.reset_password",
               target_type="user", target_id=str(user_id))
    db.commit()
    return SetPasswordResponse(password=plain)
