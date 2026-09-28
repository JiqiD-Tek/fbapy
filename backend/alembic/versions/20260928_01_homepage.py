"""新增首页配置表。

Revision ID: 20260928_01
Revises: 20260924_02
Create Date: 2026-09-28
"""

from alembic import op
import sqlalchemy as sa


revision = '20260928_01'
down_revision = '20260924_02'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'u_homepage',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键 ID'),
        sa.Column('config_type', sa.String(length=32), nullable=False, comment='配置类型：banner、newest、featured'),
        sa.Column('content', sa.JSON(), nullable=False, comment='配置内容数组'),
        sa.Column('created_time', sa.DateTime(timezone=True), nullable=False, comment='创建时间'),
        sa.Column('updated_time', sa.DateTime(timezone=True), nullable=True, comment='更新时间'),
        sa.Column('deleted', sa.BigInteger(), server_default='0', nullable=False, comment='逻辑删除标记'),
        sa.Column('deleted_time', sa.DateTime(timezone=True), nullable=True, comment='删除时间'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('config_type', name='uq_homepage_type'),
        comment='首页配置表',
    )
    op.create_index('ix_u_homepage_id', 'u_homepage', ['id'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_u_homepage_id', table_name='u_homepage')
    op.drop_table('u_homepage')
