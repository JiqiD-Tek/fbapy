"""Remove the NFC batch number.

Revision ID: 20261117_01
Revises: 20261112_01
"""

import sqlalchemy as sa
from alembic import op

revision = '20261117_01'
down_revision = '20261112_01'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index('idx_toy_nfc_batch_no', table_name='u_toy_nfc')
    op.drop_column('u_toy_nfc', 'batch_no')


def downgrade() -> None:
    op.add_column(
        'u_toy_nfc',
        sa.Column('batch_no', sa.String(64), nullable=True, comment='NFC 批次号'),
    )
    op.create_index('idx_toy_nfc_batch_no', 'u_toy_nfc', ['batch_no'], unique=False)
