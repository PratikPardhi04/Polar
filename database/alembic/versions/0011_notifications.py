"""notifications + simulated alerts"""
revision = "0011_notifications"
down_revision = "0010_checkins"

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("notif_type", sa.String(32), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False, server_default="WARNING"),
        sa.Column("target_role", sa.String(32), nullable=False, server_default=""),
        sa.Column("entity_type", sa.String(64), nullable=False, server_default=""),
        sa.Column("entity_id", sa.String(128), nullable=False, server_default=""),
        sa.Column("message", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(32), nullable=False, server_default="UNREAD"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "simulated_alerts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("recipient", sa.String(255), nullable=False, server_default=""),
        sa.Column("subject", sa.String(255), nullable=False, server_default=""),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("entity_type", sa.String(64), nullable=False, server_default=""),
        sa.Column("entity_id", sa.String(128), nullable=False, server_default=""),
        sa.Column("label", sa.String(32), nullable=False, server_default="SIMULATED"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_table("simulated_alerts")
    op.drop_table("notifications")
