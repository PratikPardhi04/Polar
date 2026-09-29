"""inventory items + transactions"""
revision = "0005_inventory"
down_revision = "0004_cargo"

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        "inventory_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(64), nullable=False, server_default="Scientific supplies"),
        sa.Column("quantity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("unit", sa.String(32), nullable=False, server_default="pcs"),
        sa.Column("location", sa.String(128), nullable=False, server_default="Bharati"),
        sa.Column("expiry", sa.Date(), nullable=True),
        sa.Column("minimum_stock", sa.Float(), nullable=False, server_default="0"),
        sa.Column("reserved_quantity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="OK"),
    )
    op.create_table(
        "inventory_transactions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("item_id", sa.String(36), sa.ForeignKey("inventory_items.id"), nullable=False),
        sa.Column("txn_type", sa.String(32), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("location", sa.String(128), nullable=True),
        sa.Column("actor_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_table("inventory_transactions")
    op.drop_table("inventory_items")
