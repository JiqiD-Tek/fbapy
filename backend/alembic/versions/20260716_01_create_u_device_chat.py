"""create u_device_chat

Revision ID: 20260716_01
Revises: 20260708_01
Create Date: 2026-07-16 00:00:00

"""

from alembic import op
import sqlalchemy as sa

from backend.common.model import TimeZone, UniversalText


# revision identifiers, used by Alembic.
revision = '20260716_01'
down_revision = '20260708_01'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'u_device_chat',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键 ID'),
        sa.Column('device_id', sa.BigInteger(), nullable=False, comment='设备ID'),
        sa.Column('toy_id', sa.BigInteger(), nullable=False, comment='玩偶ID'),
        sa.Column('user_message', UniversalText(), nullable=False, comment='用户消息内容'),
        sa.Column('reply_message', UniversalText(), nullable=False, comment='回复内容'),
        sa.Column('user_id', sa.BigInteger(), nullable=True, comment='用户ID'),
        sa.Column('baby_id', sa.BigInteger(), nullable=True, comment='宝宝ID'),
        sa.Column('created_time', TimeZone(), nullable=False, comment='创建时间'),
        sa.Column('updated_time', TimeZone(), nullable=True, comment='更新时间'),
        sa.Column('deleted', sa.BigInteger(), server_default='0', nullable=False, comment='是否已删除（0：否；id：是）'),
        sa.Column('deleted_time', TimeZone(), nullable=True, comment='删除时间'),
        sa.PrimaryKeyConstraint('id'),
        comment='设备聊天记录表',
    )
    op.create_index(op.f('ix_u_device_chat_id'), 'u_device_chat', ['id'], unique=True)
    op.create_index('idx_device_chat_device_time', 'u_device_chat', ['device_id', 'created_time'], unique=False)
    op.create_index(
        'idx_device_chat_device_toy_time',
        'u_device_chat',
        ['device_id', 'toy_id', 'created_time'],
        unique=False,
    )
    op.create_index('idx_device_chat_user_time', 'u_device_chat', ['user_id', 'created_time'], unique=False)
    op.create_index('idx_device_chat_baby_time', 'u_device_chat', ['baby_id', 'created_time'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_device_chat_baby_time', table_name='u_device_chat')
    op.drop_index('idx_device_chat_user_time', table_name='u_device_chat')
    op.drop_index('idx_device_chat_device_toy_time', table_name='u_device_chat')
    op.drop_index('idx_device_chat_device_time', table_name='u_device_chat')
    op.drop_index(op.f('ix_u_device_chat_id'), table_name='u_device_chat')
    op.drop_table('u_device_chat')
