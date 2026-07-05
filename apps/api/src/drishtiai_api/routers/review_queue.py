"""
Review queue — human-in-the-loop correction of low-confidence OCR reads.

Low-confidence reads (conf < PIPELINE_OCR_CONFIDENCE_THRESHOLD) land here
instead of being silently discarded.  Guards correct plates via this UI;
corrections are persisted back to the DB and written to
ml/plate-ocr/corrections/ as labelled training data.
"""
import pathlib
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from sqlalchemy import select, and_

from drishtiai_shared.models.review_queue import ReviewQueueItem, ReviewQueueStatus
from drishtiai_shared.models.user import UserRole
from drishtiai_api.deps import CurrentUser, DbSession, require_role
from drishtiai_api.schemas import RequestModel
from drishtiai_api.storage import get_presigned_url
from drishtiai_api.config import settings

router = APIRouter()

_CORRECTIONS_DIR = pathlib.Path("ml/plate-ocr/corrections")


class ReviewQueueOut(BaseModel):
    id: uuid.UUID
    site_id: uuid.UUID
    camera_id: uuid.UUID
    event_id: uuid.UUID | None
    ts: datetime
    snapshot_url: str | None
    raw_text: str
    raw_confidence: float
    corrected_text: str | None
    status: ReviewQueueStatus
    reviewed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReviewQueuePatch(RequestModel):
    corrected_text: str | None = Field(
        default=None,
        min_length=3,
        max_length=32,
        pattern=r"^[A-Z0-9]+$",
        description="Corrected plate text (uppercase, alphanumeric). Required when status=corrected.",
    )
    status: ReviewQueueStatus


async def _build_out(item: ReviewQueueItem) -> ReviewQueueOut:
    snapshot_url: str | None = None
    if item.snapshot_key:
        try:
            snapshot_url = await get_presigned_url(
                settings.minio_bucket_snapshots,
                item.snapshot_key,
            )
        except FileNotFoundError:
            pass

    return ReviewQueueOut(
        id=item.id,
        site_id=item.site_id,
        camera_id=item.camera_id,
        event_id=item.event_id,
        ts=item.ts,
        snapshot_url=snapshot_url,
        raw_text=item.raw_text,
        raw_confidence=item.raw_confidence,
        corrected_text=item.corrected_text,
        status=item.status,
        reviewed_at=item.reviewed_at,
        created_at=item.created_at,
    )


@router.get("", response_model=list[ReviewQueueOut])
async def list_review_queue(
    current_user: CurrentUser,
    db: DbSession,
    item_status: Annotated[ReviewQueueStatus, Query(alias="status")] = ReviewQueueStatus.pending,
    site_id: Annotated[uuid.UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[ReviewQueueOut]:
    filters = [ReviewQueueItem.status == item_status]
    if site_id:
        filters.append(ReviewQueueItem.site_id == site_id)

    q = (
        select(ReviewQueueItem)
        .where(and_(*filters))
        .order_by(ReviewQueueItem.created_at.asc())
        .limit(limit)
    )
    items = list(db.scalars(q).all())
    return [await _build_out(item) for item in items]


@router.get("/{item_id}", response_model=ReviewQueueOut)
async def get_review_item(
    item_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
) -> ReviewQueueOut:
    item = db.get(ReviewQueueItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return await _build_out(item)


@router.patch("/{item_id}", response_model=ReviewQueueOut)
async def update_review_item(
    item_id: uuid.UUID,
    body: ReviewQueuePatch,
    current_user: CurrentUser,
    db: DbSession,
) -> ReviewQueueOut:
    item = db.get(ReviewQueueItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    if item.status != ReviewQueueStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Item has already been reviewed",
        )

    if body.status == ReviewQueueStatus.corrected:
        if not body.corrected_text:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="corrected_text is required when status=corrected",
            )
        item.corrected_text = body.corrected_text
        _persist_correction(item)

    item.status = body.status
    item.reviewed_by = current_user.id
    item.reviewed_at = datetime.utcnow()

    db.commit()
    db.refresh(item)
    return await _build_out(item)


def _persist_correction(item: ReviewQueueItem) -> None:
    """Write correction to ml/plate-ocr/corrections/ for model training."""
    try:
        _CORRECTIONS_DIR.mkdir(parents=True, exist_ok=True)
        stem = str(item.id)
        (_CORRECTIONS_DIR / f"{stem}.txt").write_text(
            f"{item.corrected_text}\n{item.raw_text}\n{item.raw_confidence:.4f}\n",
            encoding="utf-8",
        )
    except Exception:
        # Non-fatal — correction is already in the DB
        pass
