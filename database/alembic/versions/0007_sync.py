"""sync receipts + conflicts"""
revision = "0007_sync"
down_revision = "0006_assets"

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        "synced_events",
        sa.Column("event_id", sa.String(128), primary_key=True),
        sa.Column("device_id", sa.String(128), nullable=False, server_default=""),
        sa.Column("user_id", sa.String(128), nullable=False, server_default=""),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(256), nullable=False, server_default=""),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("result", sa.String(32), nullable=False, server_default="ACKNOWLEDGED"),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "sync_conflicts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("entity_type", sa.String(64), nullable=False, server_default="InventoryItem"),
        sa.Column("entity_id", sa.String(128), nullable=False, server_default=""),
        sa.Column("event_ids", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(32), nullable=False, server_default="OPEN"),
        sa.Column("resolution", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_table("sync_conflicts")
    op.drop_table("synced_events")
