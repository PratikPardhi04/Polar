"""stations + expeditions"""
revision = "0002_stations_expeditions"
down_revision = "0001_init"

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        "stations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.create_table(
        "expeditions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("primary_station_id", sa.String(36), sa.ForeignKey("stations.id"), nullable=False),
        sa.Column("mission_type", sa.String(128), nullable=False, server_default="Polar Environmental Monitoring"),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source", sa.String(32), nullable=False, server_default="SYNTHETIC_DEMO"),
    )


def downgrade():
    op.drop_table("expeditions")
    op.drop_table("stations")
