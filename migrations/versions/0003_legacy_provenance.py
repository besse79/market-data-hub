"""Represent legacy bars without fabricated point-in-time availability dates.

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

def upgrade():
    op.alter_column("eod_bars", "published_at", existing_type=sa.DateTime(timezone=True), nullable=True)
    op.alter_column("eod_bars", "first_available_at", existing_type=sa.DateTime(timezone=True), nullable=True)
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_check_constraints("eod_bars")}
    if "bar_provenance_timestamps" not in existing:
        op.create_check_constraint(
            "bar_provenance_timestamps", "eod_bars",
            "(quality_status = 'legacy_unverified' AND published_at IS NULL AND first_available_at IS NULL) "
            "OR (quality_status <> 'legacy_unverified' AND published_at IS NOT NULL AND first_available_at IS NOT NULL)",
        )

def downgrade():
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT EXISTS (SELECT 1 FROM eod_bars WHERE published_at IS NULL OR first_available_at IS NULL)")).scalar():
        raise RuntimeError("Cannot downgrade: legacy bars have unknown publication dates")
    op.drop_constraint("bar_provenance_timestamps", "eod_bars", type_="check")
    op.alter_column("eod_bars", "published_at", existing_type=sa.DateTime(timezone=True), nullable=False)
    op.alter_column("eod_bars", "first_available_at", existing_type=sa.DateTime(timezone=True), nullable=False)
