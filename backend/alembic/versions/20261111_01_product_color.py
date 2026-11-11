"""Add the product theme color.

Revision ID: 20261111_01
Revises: 20261023_01
"""

from alembic import op
import sqlalchemy as sa


revision = '20261111_01'
down_revision = '20261023_01'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'u_product',
        sa.Column('color', sa.String(32), nullable=True, comment='商品主题颜色'),
    )


def downgrade() -> None:
    op.drop_column('u_product', 'color')
