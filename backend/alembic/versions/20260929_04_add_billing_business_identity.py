"""为账务流水增加业务类型和业务幂等标识。

Revision ID: 20260929_04
Revises: 20260929_03
"""

from alembic import op
import sqlalchemy as sa


revision = '20260929_04'
down_revision = '20260929_03'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'u_bill_txn',
        sa.Column('biz_type', sa.String(16), nullable=True, comment='业务类型：CHAT、STORY'),
    )
    op.add_column(
        'u_bill_txn',
        sa.Column('biz_id', sa.String(256), nullable=True, comment='业务幂等标识'),
    )
    op.execute(
        sa.text(
            "UPDATE u_bill_txn "
            "SET biz_type = 'CHAT', biz_id = CONCAT(session_id, ':', sentence_id) "
            "WHERE biz_type IS NULL OR biz_id IS NULL"
        )
    )
    op.alter_column('u_bill_txn', 'biz_type', existing_type=sa.String(16), nullable=False)
    op.alter_column('u_bill_txn', 'biz_id', existing_type=sa.String(256), nullable=False)
    op.create_unique_constraint('uk_txn_biz', 'u_bill_txn', ['biz_type', 'biz_id'])


def downgrade() -> None:
    op.drop_constraint('uk_txn_biz', 'u_bill_txn', type_='unique')
    op.drop_column('u_bill_txn', 'biz_id')
    op.drop_column('u_bill_txn', 'biz_type')
