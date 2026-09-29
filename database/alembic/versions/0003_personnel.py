"""personnel + readiness events"""
revision = "0003_personnel"
down_revision = "0002_stations_expeditions"

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        "personnel",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(64), nullable=True),
        sa.Column("role", sa.String(64), nullable=False, server_default="SCIENTIST"),
        sa.Column("expedition_id", sa.String(64), sa.ForeignKey("expeditions.id"), nullable=True),
        sa.Column("current_readiness", sa.String(32), nullable=False, server_default="NOMINATED"),
        sa.Column("emergency_contact", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "personnel_readiness_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("personnel_id", sa.String(36), sa.ForeignKey("personnel.id"), nullable=False),
        sa.Column("from_state", sa.String(32), nullable=True),
        sa.Column("to_state", sa.String(32), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_table("personnel_readiness_events")
    op.drop_table("personnel")
