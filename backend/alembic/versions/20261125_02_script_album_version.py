"""Add the script album version number.

Revision ID: 20261125_02
Revises: 20261125_01
"""

import sqlalchemy as sa

from alembic import op

revision = '20261125_02'
down_revision = '20261125_01'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'u_script_album',
        sa.Column('version', sa.Integer(), nullable=False, server_default='1', comment='版本号'),
    )
    op.alter_column('u_script_album', 'version', server_default=None)


def downgrade() -> None:
    op.drop_column('u_script_album', 'version')
