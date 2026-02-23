"""add_tenant_display_rules

Revision ID: a352f64b3cff
Revises: c3f0d2v301_abac
Create Date: 2026-02-05 13:26:21.121712

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a352f64b3cff'
down_revision: Union[str, Sequence[str], None] = 'c3f0d2v301_abac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add display_rules column to tenants table."""
    op.add_column('tenants', sa.Column('display_rules', sa.Text(), 
                  server_default='{}', nullable=True))


def downgrade() -> None:
    """Remove display_rules column from tenants table."""
    op.drop_column('tenants', 'display_rules')
