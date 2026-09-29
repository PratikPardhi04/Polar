"""assets + vehicles + work orders"""
revision = "0006_assets"
down_revision = "0005_inventory"

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        "assets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("asset_type", sa.String(32), nullable=False, server_default="EQUIPMENT"),
        sa.Column("serial_number", sa.String(128), nullable=False, unique=True),
        sa.Column("location", sa.String(128), nullable=False, server_default="Goa"),
        sa.Column("owner", sa.String(255), nullable=False, server_default=""),
        sa.Column("status", sa.String(32), nullable=False, server_default="PROCURED"),
        sa.Column("last_inspection", sa.Date(), nullable=True),
        sa.Column("next_maintenance", sa.Date(), nullable=True),
        sa.Column("runtime_hours", sa.Float(), nullable=False, server_default="0"),
        sa.Column("qr_code", sa.Text(), nullable=False, server_default=""),
    )
    op.create_table(
        "vehicles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("asset_id", sa.String(36), sa.ForeignKey("assets.id"), nullable=False, unique=True),
        sa.Column("registration_number", sa.String(64), nullable=False, server_default=""),
        sa.Column("vehicle_type", sa.String(64), nullable=False, server_default="Snowmobile"),
        sa.Column("capacity", sa.String(64), nullable=False, server_default=""),
        sa.Column("fuel_type", sa.String(32), nullable=False, server_default="Diesel"),
        sa.Column("odometer_km", sa.Float(), nullable=False, server_default="0"),
    )
    op.create_table(
        "maintenance_work_orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("asset_id", sa.String(36), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("problem", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(32), nullable=False, server_default="MEDIUM"),
        sa.Column("status", sa.String(32), nullable=False, server_default="OPEN"),
        sa.Column("assigned_engineer", sa.String(255), nullable=False, server_default=""),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_table("maintenance_work_orders")
    op.drop_table("vehicles")
    op.drop_table("assets")
