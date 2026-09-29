"""weather snapshots"""
revision = "0009_weather"
down_revision = "0008_missions"

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        "weather_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("station_id", sa.String(36), sa.ForeignKey("stations.id"), nullable=False),
        sa.Column("temp_c", sa.Float(), nullable=False),
        sa.Column("wind_kph", sa.Float(), nullable=False),
        sa.Column("visibility_m", sa.Float(), nullable=True),
        sa.Column("condition", sa.String(32), nullable=False, server_default="UNKNOWN"),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False, server_default="LIVE_API"),
    )


def downgrade():
    op.drop_table("weather_snapshots")
