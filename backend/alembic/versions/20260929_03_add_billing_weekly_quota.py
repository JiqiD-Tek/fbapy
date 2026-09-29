"""为计费账户增加自然周额度字段。

Revision ID: 20260929_03
Revises: 20260929_02
Create Date: 2026-09-29
"""

from alembic import op
import sqlalchemy as sa


revision = '20260929_03'
down_revision = '20260929_02'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'u_bill_account',
        sa.Column(
            'weekly_token_quota',
            sa.BigInteger(),
            nullable=True,
            server_default='0',
            comment='周赠送 token 额度，NULL 表示不限制',
        ),
    )
    op.add_column(
        'u_bill_account',
        sa.Column(
            'weekly_token_usage',
            sa.BigInteger(),
            nullable=False,
            server_default='0',
            comment='当前周已使用的赠送 token 数量',
        ),
    )
    op.add_column(
        'u_bill_account',
        sa.Column(
            'weekly_reset_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='当前周额度周期的下一次重置时间',
        ),
    )
    op.alter_column('u_bill_account', 'weekly_token_quota', server_default=None)
    op.alter_column('u_bill_account', 'weekly_token_usage', server_default=None)


def downgrade() -> None:
    op.drop_column('u_bill_account', 'weekly_reset_at')
    op.drop_column('u_bill_account', 'weekly_token_usage')
    op.drop_column('u_bill_account', 'weekly_token_quota')
