"""Add numeric application version codes for upgrade checks."""

from alembic import op
import sqlalchemy as sa


revision = '20261023_01'
down_revision = '20260930_02'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # NULL is the canonical value for a global application release.
    op.execute(sa.text("UPDATE u_app SET market_code = NULL WHERE market_code = 'global'"))
    op.add_column(
        'u_app',
        sa.Column('version_code', sa.Integer(), nullable=True, comment='应用版本代码'),
    )
    op.execute(sa.text('UPDATE u_app SET version_code = 0 WHERE version_code IS NULL'))
    op.alter_column(
        'u_app',
        'version_code',
        existing_type=sa.Integer(),
        existing_nullable=True,
        nullable=False,
    )
    op.create_index('ix_u_app_version_code', 'u_app', ['version_code'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_u_app_version_code', table_name='u_app')
    op.drop_column('u_app', 'version_code')
