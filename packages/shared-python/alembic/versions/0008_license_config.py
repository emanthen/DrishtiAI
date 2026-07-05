"""Add license config columns to sites; create license_clock_guard table

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add gate_expiry_mode: 'manual' (barrier stops at the state when license expired)
    # or 'freeflow' (barrier is unlocked / left open when automation stops).
    op.add_column(
        "sites",
        sa.Column(
            "gate_expiry_mode",
            sa.String(20),
            nullable=False,
            server_default="manual",
        ),
    )
    # record_on_expiry: whether to keep writing plate events after license expiry.
    # Useful for evidence / CCTV continuity; disabled by default.
    op.add_column(
        "sites",
        sa.Column(
            "record_on_expiry",
            sa.Boolean,
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("sites", "record_on_expiry")
    op.drop_column("sites", "gate_expiry_mode")
