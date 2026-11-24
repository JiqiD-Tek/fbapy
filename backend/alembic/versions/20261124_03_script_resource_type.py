"""Add resource types to script albums and scripts.

Revision ID: 20261124_03
Revises: 20261124_02
"""

import sqlalchemy as sa
from alembic import op

revision = '20261124_03'
down_revision = '20261124_02'
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ('u_script_album', 'u_script'):
        op.add_column(
            table,
            sa.Column(
                'resource_type',
                sa.SmallInteger(),
                nullable=False,
                server_default='0',
                comment='资源类型：0 普通资源，1 彩蛋资源',
            ),
        )
        op.create_index(f'ix_{table}_resource_type', table, ['resource_type'], unique=False)
        op.alter_column(table, 'resource_type', server_default=None)


def downgrade() -> None:
    for table in ('u_script', 'u_script_album'):
        op.drop_index(f'ix_{table}_resource_type', table_name=table)
        op.drop_column(table, 'resource_type')
