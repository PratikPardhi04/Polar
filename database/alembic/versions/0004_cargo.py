"""cargo hierarchy + documents"""
revision = "0004_cargo"
down_revision = "0003_personnel"

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        "shipments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("expedition_id", sa.String(64), sa.ForeignKey("expeditions.id"), nullable=False),
        sa.Column("origin", sa.String(128), nullable=False, server_default="Goa"),
        sa.Column("destination", sa.String(128), nullable=False, server_default="Bharati"),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("current_location", sa.String(128), nullable=False, server_default="Goa"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "containers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("shipment_id", sa.String(36), sa.ForeignKey("shipments.id"), nullable=False),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("location", sa.String(128), nullable=False, server_default="Goa"),
    )
    op.create_table(
        "packages",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("container_id", sa.String(36), sa.ForeignKey("containers.id"), nullable=False),
        sa.Column("shipment_id", sa.String(36), sa.ForeignKey("shipments.id"), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("weight_kg", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("location", sa.String(128), nullable=False, server_default="Goa"),
        sa.Column("qr_code", sa.Text(), nullable=False, server_default=""),
    )
    op.create_table(
        "cargo_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("package_id", sa.String(32), sa.ForeignKey("packages.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False, server_default="1"),
        sa.Column("unit", sa.String(32), nullable=False, server_default="pcs"),
        sa.Column("category", sa.String(64), nullable=False, server_default="Scientific supplies"),
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("shipment_id", sa.String(36), sa.ForeignKey("shipments.id"), nullable=False),
        sa.Column("package_id", sa.String(32), sa.ForeignKey("packages.id"), nullable=True),
        sa.Column("doc_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="GENERATED"),
        sa.Column("pdf_path", sa.String(512), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_table("documents")
    op.drop_table("cargo_items")
    op.drop_table("packages")
    op.drop_table("containers")
    op.drop_table("shipments")
