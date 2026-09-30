"""统一账务积分字段命名。

Revision ID: 20260930_01
Revises: 20260929_04
"""

from alembic import op
import sqlalchemy as sa


revision = '20260930_01'
down_revision = '20260929_04'
branch_labels = None
depends_on = None


def upgrade() -> None:
    account_columns = (
        ('balance_token', 'balance_credits', False),
        ('weekly_token_quota', 'weekly_credits_quota', True),
        ('weekly_token_usage', 'weekly_credits_usage', False),
    )
    for old_name, new_name, nullable in account_columns:
        op.alter_column(
            'u_bill_account',
            old_name,
            existing_type=sa.BigInteger(),
            existing_nullable=nullable,
            new_column_name=new_name,
        )

    txn_columns = (
        ('amount_token', 'amount_credits', False),
        ('balance_token', 'balance_credits', False),
    )
    for old_name, new_name, nullable in txn_columns:
        op.alter_column(
            'u_bill_txn',
            old_name,
            existing_type=sa.BigInteger(),
            existing_nullable=nullable,
            new_column_name=new_name,
        )


def downgrade() -> None:
    txn_columns = (
        ('amount_credits', 'amount_token', False),
        ('balance_credits', 'balance_token', False),
    )
    for old_name, new_name, nullable in txn_columns:
        op.alter_column(
            'u_bill_txn',
            old_name,
            existing_type=sa.BigInteger(),
            existing_nullable=nullable,
            new_column_name=new_name,
        )

    account_columns = (
        ('balance_credits', 'balance_token', False),
        ('weekly_credits_quota', 'weekly_token_quota', True),
        ('weekly_credits_usage', 'weekly_token_usage', False),
    )
    for old_name, new_name, nullable in account_columns:
        op.alter_column(
            'u_bill_account',
            old_name,
            existing_type=sa.BigInteger(),
            existing_nullable=nullable,
            new_column_name=new_name,
        )
