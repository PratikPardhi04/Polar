"""check-ins + comms + incidents (+ mission grace_minutes)"""
revision = "0010_checkins"
down_revision = "0009_weather"

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        "field_check_ins",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("mission_id", sa.String(32), sa.ForeignKey("field_missions.id"), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="CHECK_IN_DUE"),
        sa.Column("checked_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("location", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "mission_comms",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("mission_id", sa.String(32), sa.ForeignKey("field_missions.id"), nullable=False),
        sa.Column("author", sa.String(255), nullable=False, server_default=""),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "incidents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("incident_type", sa.String(32), nullable=False),
        sa.Column("personnel_id", sa.String(36), sa.ForeignKey("personnel.id"), nullable=True),
        sa.Column("mission_id", sa.String(32), sa.ForeignKey("field_missions.id"), nullable=True),
        sa.Column("check_in_id", sa.String(36), sa.ForeignKey("field_check_ins.id"), nullable=True),
        sa.Column("last_location", sa.String(128), nullable=False, server_default=""),
        sa.Column("detail", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(32), nullable=False, server_default="OPEN"),
        sa.Column("sos_flag", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.add_column("field_missions", sa.Column("grace_minutes", sa.Integer(), nullable=False, server_default="15"))


def downgrade():
    op.drop_column("field_missions", "grace_minutes")
    op.drop_table("incidents")
    op.drop_table("mission_comms")
    op.drop_table("field_check_ins")
