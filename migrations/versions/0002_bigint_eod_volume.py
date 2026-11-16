"""Widen EOD volume to BIGINT for historical imports.

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("eod_bars", "volume", existing_type=sa.Integer(), type_=sa.BigInteger(), existing_nullable=False)


def downgrade():
    bind = op.get_bind()
    too_large = bind.execute(sa.text("SELECT EXISTS(SELECT 1 FROM eod_bars WHERE volume > 2147483647 OR volume < -2147483648)")).scalar()
    if too_large:
        raise RuntimeError("Cannot downgrade: EOD volumes exceed INTEGER range")
    op.alter_column("eod_bars", "volume", existing_type=sa.BigInteger(), type_=sa.Integer(), existing_nullable=False)
