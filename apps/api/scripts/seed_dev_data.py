"""
Seed a minimal dev environment: one site + one ANPR camera pointing at mediamtx.

Usage:
    uv run python apps/api/scripts/seed_dev_data.py

Reads from environment:
    DATABASE_URL  (default: postgresql+psycopg://drishtiai:drishtiai@localhost:5432/drishtiai)
    RTSP_URL      (default: rtsp://mediamtx:8554/test)
    SITE_NAME     (default: Dev Site)

Safe to run multiple times — skips records that already exist.
"""
import os
import sys
import uuid

from sqlalchemy import select

from drishtiai_shared.db import SessionLocal
from drishtiai_shared.models.camera import Camera, CameraKind, CameraRole, HealthStatus
from drishtiai_shared.models.organization import Organization, PlanTier
from drishtiai_shared.models.site import Site
from drishtiai_shared.models.user import User, UserRole
from drishtiai_api.auth.password import hash_password


RTSP_URL  = os.getenv("RTSP_URL", "rtsp://mediamtx:8554/test")
SITE_NAME = os.getenv("SITE_NAME", "Dev Site")


def main() -> None:
    with SessionLocal() as db:
        # Ensure an org exists
        org = db.scalar(select(Organization).limit(1))
        if org is None:
            org = Organization(
                id=uuid.uuid4(),
                name="Dev Organization",
                plan_tier=PlanTier.smb,
            )
            db.add(org)
            db.flush()
            print(f"Created org: {org.name}  ({org.id})")
        else:
            print(f"Using existing org: {org.name}  ({org.id})")

        # Ensure superadmin exists
        admin = db.scalar(select(User).where(User.role == UserRole.superadmin).limit(1))
        if admin is None:
            password = os.getenv("SUPERADMIN_PASSWORD", "devpassword123")
            admin = User(
                id=uuid.uuid4(),
                org_id=org.id,
                site_ids=[],
                role=UserRole.superadmin,
                name="Dev Admin",
                email=os.getenv("SUPERADMIN_EMAIL", "admin@drishtiai.local"),
                password_hash=hash_password(password),
                is_active=True,
            )
            db.add(admin)
            db.flush()
            print(f"Created superadmin: {admin.email}")

        # Ensure dev site exists
        site = db.scalar(select(Site).where(Site.name == SITE_NAME).limit(1))
        if site is None:
            site = Site(
                id=uuid.uuid4(),
                org_id=org.id,
                name=SITE_NAME,
                address="Dev Environment",
                timezone="Asia/Kathmandu",
                plate_region="NP",
            )
            db.add(site)
            db.flush()
            print(f"Created site: {site.name}  ({site.id})")
        else:
            print(f"Using existing site: {site.name}  ({site.id})")

        # Ensure test camera exists
        cam = db.scalar(
            select(Camera).where(Camera.stream_url == RTSP_URL).limit(1)
        )
        if cam is None:
            cam = Camera(
                id=uuid.uuid4(),
                site_id=site.id,
                name="Dev Test Camera (mediamtx)",
                kind=CameraKind.ip,
                stream_url=RTSP_URL,
                role=CameraRole.anpr_lane,
                health_status=HealthStatus.unknown,
                enabled=True,
            )
            db.add(cam)
            db.flush()
            print(f"Created camera: {cam.name}  ({cam.id})")
            print(f"  stream_url: {cam.stream_url}")
        else:
            print(f"Using existing camera: {cam.name}  ({cam.id})")

        db.commit()
        print("\nDev seed complete.")
        print(f"  Org:     {org.id}")
        print(f"  Site:    {site.id}")
        print(f"  Camera:  {cam.id}")
        print(f"\nLogin: {admin.email} / {os.getenv('SUPERADMIN_PASSWORD', 'devpassword123')}")


if __name__ == "__main__":
    main()
