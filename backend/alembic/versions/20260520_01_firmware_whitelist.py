"""add firmware whitelist support

Revision ID: 20260520_01
Revises: None
Create Date: 2026-05-20 12:00:00

"""

from alembic import op
import sqlalchemy as sa
import backend.common.model


# revision identifiers, used by Alembic.
revision = '20260520_01'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'u_firmware',
        sa.Column(
            'release_scope',
            sa.String(length=16),
            nullable=False,
            server_default='public',
            comment='发布范围 public=公开 whitelist=白名单',
        ),
    )
    op.create_index(op.f('ix_u_firmware_release_scope'), 'u_firmware', ['release_scope'], unique=False)

    op.create_table(
        'u_firmware_whitelist',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键 ID'),
        sa.Column('firmware_id', sa.BigInteger(), nullable=False, comment='固件 ID'),
        sa.Column('device_did', sa.String(length=64), nullable=False, comment='设备 DID'),
        sa.Column('enabled', sa.Boolean(), nullable=False, comment='是否启用'),
        sa.Column('allow_downgrade', sa.Boolean(), nullable=False, comment='是否允许降级到目标固件'),
        sa.Column('expires_at', backend.common.model.TimeZone(), nullable=True, comment='过期时间'),
        sa.Column('remark', sa.String(length=500), nullable=True, comment='备注'),
        sa.Column('created_time', backend.common.model.TimeZone(), nullable=False, comment='创建时间'),
        sa.Column('updated_time', backend.common.model.TimeZone(), nullable=True, comment='更新时间'),
        sa.PrimaryKeyConstraint('id'),
        comment='固件白名单表',
    )
    op.create_index(op.f('ix_u_firmware_whitelist_device_did'), 'u_firmware_whitelist', ['device_did'], unique=True)
    op.create_index(op.f('ix_u_firmware_whitelist_enabled'), 'u_firmware_whitelist', ['enabled'], unique=False)
    op.create_index(op.f('ix_u_firmware_whitelist_firmware_id'), 'u_firmware_whitelist', ['firmware_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_u_firmware_whitelist_firmware_id'), table_name='u_firmware_whitelist')
    op.drop_index(op.f('ix_u_firmware_whitelist_enabled'), table_name='u_firmware_whitelist')
    op.drop_index(op.f('ix_u_firmware_whitelist_device_did'), table_name='u_firmware_whitelist')
    op.drop_table('u_firmware_whitelist')

    op.drop_index(op.f('ix_u_firmware_release_scope'), table_name='u_firmware')
    op.drop_column('u_firmware', 'release_scope')
