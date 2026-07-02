"""Initial schema — all canonical entities

Revision ID: 0001
Revises:
Create Date: 2026-07-02
"""
from typing import Sequence, Union
import sqlalchemy as sa
import geoalchemy2
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # organizations
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("contact_email", sa.String(255)),
        sa.Column("contact_phone", sa.String(50)),
        sa.Column("plan_tier", sa.String(20), nullable=False, server_default="smb"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # users (before sites — sites FK references users)
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("site_ids", postgresql.ARRAY(sa.String), server_default="{}"),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("phone", sa.String(50)),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("mfa_secret", sa.String(64)),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # sites
    op.create_table(
        "sites",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("address", sa.String(500)),
        sa.Column("geo", geoalchemy2.Geography(geometry_type="POINT", srid=4326)),
        sa.Column("timezone", sa.String(64), server_default="Asia/Kathmandu"),
        sa.Column("plate_region", sa.String(10), server_default="NP"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # cameras
    op.create_table(
        "cameras",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(20), server_default="ip"),
        sa.Column("stream_url", sa.String(1024)),
        sa.Column("resolution_w", sa.Integer),
        sa.Column("resolution_h", sa.Integer),
        sa.Column("fps", sa.Float),
        sa.Column("gpu_slot", sa.Integer),
        sa.Column("role", sa.String(30), server_default="general"),
        sa.Column("ptz", sa.Boolean, server_default="false"),
        sa.Column("onvif_profile", sa.String(64)),
        sa.Column("health_status", sa.String(20), server_default="unknown"),
        sa.Column("geo", geoalchemy2.Geography(geometry_type="POINT", srid=4326)),
        sa.Column("enabled", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # zones
    op.create_table(
        "zones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("camera_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("purpose", sa.String(30), nullable=False),
        sa.Column("geometry_json", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # vehicles
    op.create_table(
        "vehicles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("first_seen", sa.DateTime(timezone=True)),
        sa.Column("last_seen", sa.DateTime(timezone=True)),
        sa.Column("type", sa.String(30)),
        sa.Column("type_confidence", sa.Float),
        sa.Column("make", sa.String(100)),
        sa.Column("model", sa.String(100)),
        sa.Column("make_model_confidence", sa.Float),
        sa.Column("color", sa.String(30)),
        sa.Column("color_confidence", sa.Float),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # plates
    op.create_table(
        "plates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("text", sa.String(30), nullable=False),
        sa.Column("region", sa.String(10)),
        sa.Column("format_class", sa.String(20), server_default="unknown"),
        sa.Column("vehicle_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vehicles.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_plates_text", "plates", ["text"])
    op.execute("CREATE INDEX ix_plates_text_trgm ON plates USING gin (text gin_trgm_ops)")

    # events (partitioned by ts monthly — create parent table + default partition)
    op.execute("""
        CREATE TABLE events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            site_id UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
            camera_id UUID NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
            ts TIMESTAMPTZ NOT NULL,
            kind VARCHAR(30) NOT NULL,
            vehicle_id UUID REFERENCES vehicles(id) ON DELETE SET NULL,
            plate_id UUID REFERENCES plates(id) ON DELETE SET NULL,
            snapshot_key VARCHAR(512),
            clip_key VARCHAR(512),
            confidence FLOAT,
            meta_json JSONB,
            created_at TIMESTAMPTZ DEFAULT now()
        ) PARTITION BY RANGE (ts)
    """)
    op.execute("CREATE TABLE events_default PARTITION OF events DEFAULT")
    op.execute("CREATE INDEX ix_events_site_kind_ts ON events (site_id, kind, ts)")
    op.execute("CREATE INDEX ix_events_ts ON events (ts)")

    # watchlists
    op.create_table(
        "watchlists",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("alert_channels", postgresql.ARRAY(sa.String), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # watchlist_entries
    op.create_table(
        "watchlist_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("watchlist_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("watchlists.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plate_text", sa.String(30), nullable=False),
        sa.Column("plate_pattern", sa.String(20), server_default="exact"),
        sa.Column("notes", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # alerts
    op.create_table(
        "alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("watchlist_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("watchlists.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(20), server_default="new"),
        sa.Column("ack_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("ack_at", sa.DateTime(timezone=True)),
        sa.Column("snooze_until", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # parking_sessions
    op.create_table(
        "parking_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("plates.id", ondelete="SET NULL")),
        sa.Column("entry_event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("events.id", ondelete="SET NULL")),
        sa.Column("exit_event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("events.id", ondelete="SET NULL")),
        sa.Column("duration_s", sa.Integer),
        sa.Column("tariff_snapshot", postgresql.JSONB),
        sa.Column("amount_due", sa.Float),
        sa.Column("payment_status", sa.String(20), server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # permits
    op.create_table(
        "permits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("plates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("issued_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # tariffs
    op.create_table(
        "tariffs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("rules_json", postgresql.JSONB, nullable=False),
        sa.Column("active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # visitor_passes
    op.create_table(
        "visitor_passes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("host_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("plate", sa.String(30), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=False),
        sa.Column("single_use", sa.Boolean, server_default="true"),
        sa.Column("used", sa.Boolean, server_default="false"),
        sa.Column("notes", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # audit_logs
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(100)),
        sa.Column("target_id", sa.String(64)),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ip", postgresql.INET),
        sa.Column("meta_json", postgresql.JSONB),
    )
    op.create_index("ix_audit_logs_ts", "audit_logs", ["ts"])
    op.create_index("ix_audit_logs_actor", "audit_logs", ["actor_user_id"])

    # retention_policies
    op.create_table(
        "retention_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("data_class", sa.String(40), nullable=False),
        sa.Column("retain_days", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("retention_policies")
    op.drop_table("audit_logs")
    op.drop_table("visitor_passes")
    op.drop_table("tariffs")
    op.drop_table("permits")
    op.drop_table("parking_sessions")
    op.drop_table("alerts")
    op.drop_table("watchlist_entries")
    op.drop_table("watchlists")
    op.execute("DROP TABLE IF EXISTS events CASCADE")
    op.drop_table("plates")
    op.drop_table("vehicles")
    op.drop_table("zones")
    op.drop_table("cameras")
    op.drop_table("sites")
    op.drop_table("users")
    op.drop_table("organizations")
