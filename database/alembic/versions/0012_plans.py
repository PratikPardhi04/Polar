"""plan drafts"""
revision = "0012_plans"
down_revision = "0011_notifications"

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        "plan_drafts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False, server_default="GENERAL"),
        sa.Column("body", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_table("plan_drafts")
