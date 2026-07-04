"""Webhook subscription table

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-04
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "webhooks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("site_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("secret", sa.String(256), nullable=True),
        sa.Column("events", postgresql.ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status_code", sa.Integer, nullable=True),
    )
    op.create_index("ix_webhooks_site_id", "webhooks", ["site_id"])


def downgrade() -> None:
    op.drop_index("ix_webhooks_site_id", table_name="webhooks")
    op.drop_table("webhooks")
