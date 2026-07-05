"""Add plate_region to cameras; create review_queue table.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-05
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cameras",
        sa.Column("plate_region", sa.String(20), nullable=False, server_default="auto"),
    )

    op.create_table(
        "review_queue",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("camera_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("events.id", ondelete="SET NULL"), nullable=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("snapshot_key", sa.String(1024), nullable=True),
        sa.Column("raw_text", sa.String(64), nullable=False),
        sa.Column("raw_confidence", sa.Float(), nullable=False),
        sa.Column("corrected_text", sa.String(64), nullable=True),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_review_queue_status_created", "review_queue", ["status", "created_at"])
    op.create_index("ix_review_queue_site_status", "review_queue", ["site_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_review_queue_site_status", table_name="review_queue")
    op.drop_index("ix_review_queue_status_created", table_name="review_queue")
    op.drop_table("review_queue")
    op.drop_column("cameras", "plate_region")
