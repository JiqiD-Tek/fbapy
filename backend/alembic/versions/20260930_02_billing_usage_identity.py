"""按业务、业务标识和用量类型建立账务幂等标识。

Revision ID: 20260930_02
Revises: 20260930_01
"""

from alembic import op
import sqlalchemy as sa


revision = '20260930_02'
down_revision = '20260930_01'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'u_bill_txn',
        sa.Column('usage_type', sa.String(32), nullable=True, comment='原始用量类型'),
    )
    op.execute(
        sa.text(
            "UPDATE u_bill_txn SET usage_type = 'legacy' "
            "WHERE usage_type IS NULL"
        )
    )
    op.alter_column(
        'u_bill_txn',
        'usage_type',
        existing_type=sa.String(32),
        nullable=False,
    )
    op.drop_constraint('uk_txn_sentence', 'u_bill_txn', type_='unique')
    op.drop_constraint('uk_txn_biz', 'u_bill_txn', type_='unique')
    op.create_unique_constraint(
        'uk_txn_biz_usage',
        'u_bill_txn',
        ['biz_type', 'biz_id', 'usage_type'],
    )


def downgrade() -> None:
    op.drop_constraint('uk_txn_biz_usage', 'u_bill_txn', type_='unique')
    op.create_unique_constraint('uk_txn_biz', 'u_bill_txn', ['biz_type', 'biz_id'])
    op.create_unique_constraint('uk_txn_sentence', 'u_bill_txn', ['session_id', 'sentence_id'])
    op.drop_column('u_bill_txn', 'usage_type')
