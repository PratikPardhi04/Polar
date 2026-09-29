"""mission + phase reports"""
revision = "0014_reports"
down_revision = "0013_situation"

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        "mission_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("mission_id", sa.String(32), sa.ForeignKey("field_missions.id"), nullable=False, unique=True),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("closing_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("html", sa.Text(), nullable=False, server_default=""),
        sa.Column("pdf_path", sa.String(512), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "phase_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("expedition_id", sa.String(64), sa.ForeignKey("expeditions.id"), nullable=False),
        sa.Column("phase_name", sa.String(128), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("rollup", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("pdf_path", sa.String(512), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_table("phase_reports")
    op.drop_table("mission_reports")
