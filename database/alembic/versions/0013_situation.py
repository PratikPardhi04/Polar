"""situation reports"""
revision = "0013_situation"
down_revision = "0012_plans"

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        "situation_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("expedition_id", sa.String(64), sa.ForeignKey("expeditions.id"), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("sections", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("published_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_table("situation_reports")
