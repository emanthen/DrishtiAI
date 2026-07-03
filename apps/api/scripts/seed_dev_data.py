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
from drishtiai_shared.models.parking import Tariff
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

        # Parking entry camera (test2 path)
        entry_url = os.getenv("RTSP_ENTRY_URL", "rtsp://mediamtx:8554/test2")
        entry_cam = db.scalar(
            select(Camera).where(Camera.stream_url == entry_url).limit(1)
        )
        if entry_cam is None:
            entry_cam = Camera(
                id=uuid.uuid4(),
                site_id=site.id,
                name="Dev Entry Camera (mediamtx/test2)",
                kind=CameraKind.ip,
                stream_url=entry_url,
                role=CameraRole.parking_entry,
                health_status=HealthStatus.unknown,
                enabled=True,
            )
            db.add(entry_cam)
            db.flush()
            print(f"Created parking_entry camera: {entry_cam.name}  ({entry_cam.id})")

        # Parking exit camera (test3 path)
        exit_url = os.getenv("RTSP_EXIT_URL", "rtsp://mediamtx:8554/test3")
        exit_cam = db.scalar(
            select(Camera).where(Camera.stream_url == exit_url).limit(1)
        )
        if exit_cam is None:
            exit_cam = Camera(
                id=uuid.uuid4(),
                site_id=site.id,
                name="Dev Exit Camera (mediamtx/test3)",
                kind=CameraKind.ip,
                stream_url=exit_url,
                role=CameraRole.parking_exit,
                health_status=HealthStatus.unknown,
                enabled=True,
            )
            db.add(exit_cam)
            db.flush()
            print(f"Created parking_exit camera: {exit_cam.name}  ({exit_cam.id})")

        # Default tariff
        tariff = db.scalar(select(Tariff).where(Tariff.site_id == site.id).limit(1))
        if tariff is None:
            tariff = Tariff(
                id=uuid.uuid4(),
                site_id=site.id,
                name="Standard Tariff",
                rules_json={
                    "currency": "NPR",
                    "grace_minutes": 10,
                    "tiers": [
                        {"up_to_minutes": 60, "charge": 30},
                        {"per_hour": 30, "max_per_day": 300},
                    ],
                },
                active=True,
            )
            db.add(tariff)
            db.flush()
            print(f"Created tariff: {tariff.name}  ({tariff.id})")

        db.commit()
        print("\nDev seed complete.")
        print(f"  Org:          {org.id}")
        print(f"  Site:         {site.id}")
        print(f"  ANPR camera:  {cam.id}")
        print(f"  Entry camera: {entry_cam.id}")
        print(f"  Exit camera:  {exit_cam.id}")
        print(f"  Tariff:       {tariff.id}")
        print(f"\nLogin: {admin.email} / {os.getenv('SUPERADMIN_PASSWORD', 'devpassword123')}")


if __name__ == "__main__":
    main()
