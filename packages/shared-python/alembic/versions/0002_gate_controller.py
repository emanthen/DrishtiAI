"""Gate controller, rules, and trigger log tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-03
"""
from typing import Sequence, Union
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "gate_controllers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False, server_default="webhook"),
        sa.Column("config", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("open_pulse_ms", sa.Integer, nullable=False, server_default="500"),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_gate_controllers_site", "gate_controllers", ["site_id"])

    op.create_table(
        "gate_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("camera_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False),
        sa.Column("gate_controller_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("gate_controllers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trigger_on", sa.String(30), nullable=False, server_default="any_plate"),
        sa.Column("watchlist_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("watchlists.id", ondelete="SET NULL")),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_gate_rules_camera", "gate_rules", ["camera_id"])

    op.create_table(
        "gate_trigger_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("gate_rule_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("gate_rules.id", ondelete="SET NULL")),
        sa.Column("gate_controller_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("gate_controllers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("events.id", ondelete="SET NULL")),
        sa.Column("plate_text", sa.String(30)),
        sa.Column("triggered_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("success", sa.Boolean, nullable=False),
        sa.Column("error_msg", sa.String(500)),
    )
    op.create_index("ix_gate_trigger_logs_controller_ts", "gate_trigger_logs", ["gate_controller_id", "triggered_at"])


def downgrade() -> None:
    op.drop_table("gate_trigger_logs")
    op.drop_table("gate_rules")
    op.drop_table("gate_controllers")
