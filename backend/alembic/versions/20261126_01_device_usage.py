"""Add device daily usage and usage events.

Revision ID: 20261126_01
Revises: 
"""

import sqlalchemy as sa

from alembic import op

revision = '20261126_01'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'u_device_usage',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('did', sa.String(64), nullable=False, comment='设备 DID'),
        sa.Column('usage_date', sa.Date(), nullable=False, comment='业务日期'),
        sa.Column('chat_seconds', sa.BigInteger(), nullable=False, server_default='0', comment='AI 对话时长，单位秒'),
        sa.Column('story_count', sa.BigInteger(), nullable=False, server_default='0', comment='AI 故事创建次数'),
        sa.Column('created_time', sa.DateTime(timezone=True), nullable=False, comment='创建时间'),
        sa.Column('updated_time', sa.DateTime(timezone=True), nullable=True, comment='更新时间'),
        sa.Column('deleted', sa.BigInteger(), nullable=False, server_default='0', comment='是否已删除'),
        sa.Column('deleted_time', sa.DateTime(timezone=True), nullable=True, comment='删除时间'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('did', 'usage_date', name='uq_device_usage_did_date'),
        comment='设备每日 AI 使用量汇总',
    )
    op.create_index('idx_device_usage_date', 'u_device_usage', ['usage_date'], unique=False)

    op.create_table(
        'u_device_usage_event',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('did', sa.String(64), nullable=False, comment='设备 DID'),
        sa.Column('event_type', sa.String(16), nullable=False, comment='事件类型：CHAT、STORY'),
        sa.Column('event_key', sa.String(256), nullable=False, comment='事件幂等标识'),
        sa.Column('usage_date', sa.Date(), nullable=False, comment='业务日期'),
        sa.Column('quantity', sa.BigInteger(), nullable=False, comment='本次使用量'),
        sa.Column('created_time', sa.DateTime(timezone=True), nullable=False, comment='创建时间'),
        sa.Column('updated_time', sa.DateTime(timezone=True), nullable=True, comment='更新时间'),
        sa.Column('deleted', sa.BigInteger(), nullable=False, server_default='0', comment='是否已删除'),
        sa.Column('deleted_time', sa.DateTime(timezone=True), nullable=True, comment='删除时间'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('event_type', 'event_key', name='uq_device_usage_event_business'),
        comment='设备使用事件幂等记录',
    )
    op.create_index(
        'idx_device_usage_event_did_time', 'u_device_usage_event', ['did', 'created_time'], unique=False,
    )


def downgrade() -> None:
    op.drop_index('idx_device_usage_event_did_time', table_name='u_device_usage_event')
    op.drop_table('u_device_usage_event')
    op.drop_index('idx_device_usage_date', table_name='u_device_usage')
    op.drop_table('u_device_usage')
