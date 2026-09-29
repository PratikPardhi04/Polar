"""field missions + members"""
revision = "0008_missions"
down_revision = "0007_sync"

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        "field_missions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("expedition_id", sa.String(64), sa.ForeignKey("expeditions.id"), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False, server_default=""),
        sa.Column("leader_id", sa.String(36), sa.ForeignKey("personnel.id"), nullable=True),
        sa.Column("vehicle_id", sa.String(36), sa.ForeignKey("vehicles.id"), nullable=True),
        sa.Column("equipment_ids", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expected_return", sa.DateTime(timezone=True), nullable=True),
        sa.Column("route", sa.Text(), nullable=False, server_default=""),
        sa.Column("check_in_interval_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("emergency_kit", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("emergency_plan", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
    )
    op.create_table(
        "field_mission_members",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("mission_id", sa.String(32), sa.ForeignKey("field_missions.id"), nullable=False),
        sa.Column("personnel_id", sa.String(36), sa.ForeignKey("personnel.id"), nullable=False),
        sa.Column("role", sa.String(64), nullable=False, server_default="MEMBER"),
    )


def downgrade():
    op.drop_table("field_mission_members")
    op.drop_table("field_missions")
