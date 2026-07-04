"""
Input-validation regression tests for PR 3 (validation/input-hardening).
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError


# ── extra="forbid" ─────────────────────────────────────────────────────────────

def test_camera_create_rejects_unknown_fields() -> None:
    from drishtiai_api.routers.cameras import CameraCreate
    import uuid

    with pytest.raises(ValidationError) as exc_info:
        CameraCreate(
            name="Test Cam",
            site_id=uuid.uuid4(),
            __hack__="injected",
        )
    assert "extra inputs are not permitted" in str(exc_info.value).lower()


def test_watchlist_create_rejects_unknown_fields() -> None:
    from drishtiai_api.routers.watchlists import WatchlistCreate
    from drishtiai_shared.models.watchlist import WatchlistCategory
    import uuid

    with pytest.raises(ValidationError):
        WatchlistCreate(
            site_id=uuid.uuid4(),
            name="VIP",
            category=WatchlistCategory.whitelist,
            __injected__=True,
        )


# ── RTSP URL validation ────────────────────────────────────────────────────────

def test_camera_create_rejects_http_stream_url() -> None:
    from drishtiai_api.routers.cameras import CameraCreate
    import uuid

    with pytest.raises(ValidationError) as exc_info:
        CameraCreate(name="Cam", site_id=uuid.uuid4(), stream_url="http://192.168.1.1/stream")
    assert "rtsp" in str(exc_info.value).lower()


def test_camera_create_accepts_rtsp_url() -> None:
    from drishtiai_api.routers.cameras import CameraCreate
    import uuid

    cam = CameraCreate(
        name="Cam",
        site_id=uuid.uuid4(),
        stream_url="rtsp://192.168.1.1:554/stream1",
    )
    assert cam.stream_url.startswith("rtsp://")


def test_camera_create_accepts_rtsps_url() -> None:
    from drishtiai_api.routers.cameras import CameraCreate
    import uuid

    cam = CameraCreate(
        name="Cam",
        site_id=uuid.uuid4(),
        stream_url="rtsps://cam.example.com/live",
    )
    assert cam.stream_url.startswith("rtsps://")


# ── Timezone validation ────────────────────────────────────────────────────────

def test_site_create_rejects_invalid_timezone() -> None:
    from drishtiai_api.routers.sites import SiteCreate
    import uuid

    with pytest.raises(ValidationError) as exc_info:
        SiteCreate(org_id=uuid.uuid4(), name="HQ", timezone="'; DROP TABLE sites; --")
    assert "timezone" in str(exc_info.value).lower()


def test_site_create_accepts_valid_timezone() -> None:
    from drishtiai_api.routers.sites import SiteCreate
    import uuid

    site = SiteCreate(org_id=uuid.uuid4(), name="HQ", timezone="Asia/Kathmandu")
    assert site.timezone == "Asia/Kathmandu"


# ── Plate normalisation ────────────────────────────────────────────────────────

def test_watchlist_entry_plate_normalised() -> None:
    from drishtiai_api.routers.watchlists import EntryCreate

    entry = EntryCreate(plate_text=" ba 12 pa 3456 ")
    assert entry.plate_text == "BA12PA3456"


def test_watchlist_entry_plate_too_long_rejected() -> None:
    from drishtiai_api.routers.watchlists import EntryCreate

    with pytest.raises(ValidationError):
        EntryCreate(plate_text="A" * 25)


# ── HTML sanitization ─────────────────────────────────────────────────────────

def test_sanitize_strips_script_tags() -> None:
    from drishtiai_api.sanitize import strip_html

    result = strip_html('<script>alert("xss")</script>Hello')
    assert "<script>" not in result
    assert "Hello" in result


def test_sanitize_strips_img_onerror() -> None:
    from drishtiai_api.sanitize import strip_html

    result = strip_html('<img src=x onerror="alert(1)">world')
    assert "<img" not in result
    assert "world" in result


def test_watchlist_create_notes_sanitized() -> None:
    from drishtiai_api.routers.watchlists import EntryCreate

    entry = EntryCreate(plate_text="BA12PA", notes='<b>VIP</b><script>x()</script>')
    assert "<script>" not in entry.notes
    assert "<b>" not in entry.notes


# ── MinIO key path traversal ───────────────────────────────────────────────────

def test_minio_key_rejects_traversal() -> None:
    from fastapi import HTTPException
    from drishtiai_api.storage import _safe_minio_key

    with pytest.raises(HTTPException) as exc_info:
        _safe_minio_key("snapshots/../../etc/passwd")
    assert exc_info.value.status_code == 400


def test_minio_key_rejects_absolute_path() -> None:
    from fastapi import HTTPException
    from drishtiai_api.storage import _safe_minio_key

    with pytest.raises(HTTPException):
        _safe_minio_key("/etc/shadow")


def test_minio_key_accepts_valid_key() -> None:
    from drishtiai_api.storage import _safe_minio_key

    assert _safe_minio_key("snapshots/site-id/cam-id/2026-07-04T12:00:00.jpg") == \
        "snapshots/site-id/cam-id/2026-07-04T12:00:00.jpg"


# ── Field length limits ────────────────────────────────────────────────────────

def test_user_create_name_max_length() -> None:
    from drishtiai_api.routers.users import UserCreate
    from drishtiai_shared.models.user import UserRole

    with pytest.raises(ValidationError):
        UserCreate(name="A" * 300, email="a@b.com", role=UserRole.guard)


def test_password_min_length_enforced() -> None:
    from drishtiai_api.routers.users import SetPasswordBody

    with pytest.raises(ValidationError):
        SetPasswordBody(password="short")
