"""
Create initial superadmin user and default organization.

Usage:
    uv run python apps/api/scripts/seed_superadmin.py

Reads from environment:
    SUPERADMIN_EMAIL    (default: admin@drishtiai.local)
    SUPERADMIN_PASSWORD (required)
    DATABASE_URL
"""
import os
import sys
import uuid

from sqlalchemy import select

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from drishtiai_shared.db import SessionLocal
from drishtiai_shared.models.organization import Organization, PlanTier
from drishtiai_shared.models.user import User, UserRole
from drishtiai_api.auth.password import hash_password


def main() -> None:
    email = os.getenv("SUPERADMIN_EMAIL", "admin@drishtiai.local")
    password = os.getenv("SUPERADMIN_PASSWORD", "")
    if not password:
        print("ERROR: SUPERADMIN_PASSWORD environment variable is required.", file=sys.stderr)
        sys.exit(1)

    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.email == email))
        if existing:
            print(f"Superadmin {email} already exists — skipping.")
            return

        org = Organization(
            id=uuid.uuid4(),
            name="Default Organization",
            plan_tier=PlanTier.smb,
        )
        db.add(org)
        db.flush()

        user = User(
            id=uuid.uuid4(),
            org_id=org.id,
            site_ids=[],
            role=UserRole.superadmin,
            name="Super Admin",
            email=email,
            password_hash=hash_password(password),
            is_active=True,
        )
        db.add(user)
        db.commit()
        print(f"Created superadmin: {email}")
        print(f"Org ID: {org.id}")
        print(f"User ID: {user.id}")


if __name__ == "__main__":
    main()
