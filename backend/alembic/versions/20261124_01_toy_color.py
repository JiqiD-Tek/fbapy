"""Add the toy theme color.

Revision ID: 20261124_01
Revises: 20261117_01
"""

import sqlalchemy as sa
from alembic import op


revision = '20261124_01'
down_revision = '20261117_01'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'u_toy',
        sa.Column('color', sa.String(32), nullable=True, comment='玩偶主题颜色'),
    )


def downgrade() -> None:
    op.drop_column('u_toy', 'color')
