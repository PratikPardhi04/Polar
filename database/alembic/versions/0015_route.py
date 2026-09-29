"""route legs"""
revision = "0015_route"
down_revision = "0014_reports"

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        "route_legs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("expedition_id", sa.String(64), sa.ForeignKey("expeditions.id"), nullable=True),
        sa.Column("seq", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("origin", sa.String(128), nullable=False),
        sa.Column("destination", sa.String(128), nullable=False),
        sa.Column("mode", sa.String(64), nullable=False, server_default="SHIP"),
        sa.Column("departure", sa.DateTime(timezone=True), nullable=True),
        sa.Column("eta", sa.DateTime(timezone=True), nullable=True),
        sa.Column("capacity", sa.String(64), nullable=False, server_default=""),
        sa.Column("status", sa.String(32), nullable=False, server_default="SCHEDULED"),
        sa.Column("delay_min", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade():
    op.drop_table("route_legs")
