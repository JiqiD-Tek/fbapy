"""add voice_language to u_cloud_role

Revision ID: 20260708_01
Revises: None
Create Date: 2026-07-08 00:00:00

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260708_01'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'u_cloud_role',
        sa.Column('voice_language', sa.String(length=32), nullable=True, comment='音色语言，如 zh-CN、en-US、zh-TW'),
    )


def downgrade():
    op.drop_column('u_cloud_role', 'voice_language')
