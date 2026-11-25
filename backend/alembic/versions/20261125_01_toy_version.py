"""Add the toy version number.

Revision ID: 20261125_01
Revises: 20261124_03
"""

import sqlalchemy as sa

from alembic import op

revision = '20261125_01'
down_revision = '20261124_03'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'u_toy',
        sa.Column('version', sa.Integer(), nullable=False, server_default='1', comment='版本号'),
    )
    op.alter_column('u_toy', 'version', server_default=None)


def downgrade() -> None:
    op.drop_column('u_toy', 'version')
