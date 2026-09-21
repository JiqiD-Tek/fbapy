"""新增玩偶 NFC 编码绑定表。

Revision ID: 20260921_01
Revises:
Create Date: 2026-09-21
"""

from alembic import op
import sqlalchemy as sa


revision = '20260921_01'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'u_toy_nfc',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键 ID'),
        sa.Column('toy_id', sa.BigInteger(), nullable=False, comment='玩偶 ID'),
        sa.Column('nfc_code', sa.String(length=64), nullable=False, comment='NFC 编码'),
        sa.Column('batch_no', sa.String(length=64), nullable=True, comment='NFC 批次号'),
        sa.Column('status', sa.SmallInteger(), nullable=False, comment='状态：0 禁用，1 启用'),
        sa.Column('remark', sa.String(length=500), nullable=True, comment='备注'),
        sa.Column('created_time', sa.DateTime(timezone=True), nullable=False, comment='创建时间'),
        sa.Column('updated_time', sa.DateTime(timezone=True), nullable=True, comment='更新时间'),
        sa.Column('deleted', sa.BigInteger(), server_default='0', nullable=False, comment='逻辑删除标记'),
        sa.Column('deleted_time', sa.DateTime(timezone=True), nullable=True, comment='删除时间'),
        sa.ForeignKeyConstraint(['toy_id'], ['u_toy.id'], name='fk_toy_nfc_toy_id', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('nfc_code', name='uq_toy_nfc_code'),
        comment='玩偶 NFC 编码绑定表',
    )
    op.create_index('ix_u_toy_nfc_id', 'u_toy_nfc', ['id'], unique=True)
    op.create_index('idx_toy_nfc_toy_id', 'u_toy_nfc', ['toy_id'], unique=False)
    op.create_index('idx_toy_nfc_batch_no', 'u_toy_nfc', ['batch_no'], unique=False)
    op.create_index('ix_u_toy_nfc_status', 'u_toy_nfc', ['status'], unique=False)

    toy = sa.table(
        'u_toy',
        sa.column('id', sa.BigInteger()),
        sa.column('nfc_code', sa.String(length=64)),
        sa.column('created_time', sa.DateTime(timezone=True)),
        sa.column('updated_time', sa.DateTime(timezone=True)),
        sa.column('deleted', sa.BigInteger()),
    )
    toy_nfc = sa.table(
        'u_toy_nfc',
        sa.column('toy_id', sa.BigInteger()),
        sa.column('nfc_code', sa.String(length=64)),
        sa.column('batch_no', sa.String(length=64)),
        sa.column('status', sa.SmallInteger()),
        sa.column('remark', sa.String(length=500)),
        sa.column('created_time', sa.DateTime(timezone=True)),
        sa.column('updated_time', sa.DateTime(timezone=True)),
        sa.column('deleted', sa.BigInteger()),
        sa.column('deleted_time', sa.DateTime(timezone=True)),
    )
    op.execute(
        sa.insert(toy_nfc).from_select(
            [
                'toy_id',
                'nfc_code',
                'batch_no',
                'status',
                'remark',
                'created_time',
                'updated_time',
                'deleted',
                'deleted_time',
            ],
            sa.select(
                toy.c.id,
                toy.c.nfc_code,
                sa.null(),
                sa.literal(1),
                sa.null(),
                toy.c.created_time,
                toy.c.updated_time,
                sa.literal(0),
                sa.null(),
            ).where(
                toy.c.deleted == 0,
                toy.c.nfc_code.is_not(None),
                toy.c.nfc_code != '',
            ),
        )
    )
    op.drop_index('ix_u_toy_nfc_code', table_name='u_toy')
    op.drop_column('u_toy', 'nfc_code')


def downgrade() -> None:
    op.add_column('u_toy', sa.Column('nfc_code', sa.String(length=64), nullable=True, comment='NFC 编码（兼容字段）'))
    bind = op.get_bind()
    rows = bind.execute(sa.text('SELECT toy_id, nfc_code FROM u_toy_nfc ORDER BY id')).mappings()
    toy_ids: set[int] = set()
    toy = sa.table('u_toy', sa.column('id', sa.BigInteger()), sa.column('nfc_code', sa.String(length=64)))
    for row in rows:
        toy_id = int(row['toy_id'])
        if toy_id in toy_ids:
            continue
        bind.execute(
            toy.update().where(toy.c.id == toy_id).values(nfc_code=row['nfc_code'])
        )
        toy_ids.add(toy_id)
    op.create_index('ix_u_toy_nfc_code', 'u_toy', ['nfc_code'], unique=True)
    op.drop_index('ix_u_toy_nfc_status', table_name='u_toy_nfc')
    op.drop_index('idx_toy_nfc_batch_no', table_name='u_toy_nfc')
    op.drop_index('idx_toy_nfc_toy_id', table_name='u_toy_nfc')
    op.drop_index('ix_u_toy_nfc_id', table_name='u_toy_nfc')
    op.drop_table('u_toy_nfc')
