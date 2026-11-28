"""Legacy Yahoo identity mapping without inventing MIC.

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "legacy_symbol_map",
        sa.Column("symbol", sa.String(80), primary_key=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("name", sa.String(250), nullable=False),
        sa.Column("instrument_id", UUID(as_uuid=True), sa.ForeignKey("instruments.id"), nullable=False, unique=True),
        sa.Column("mic", sa.String(10), nullable=True),
        sa.Column("mic_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.CheckConstraint("mic_verified = false OR mic IS NOT NULL", name="verified_mic_present"),
    )

def downgrade():
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT EXISTS (SELECT 1 FROM legacy_symbol_map)")).scalar():
        raise RuntimeError("Cannot downgrade: legacy symbol mappings exist")
    op.drop_table("legacy_symbol_map")
