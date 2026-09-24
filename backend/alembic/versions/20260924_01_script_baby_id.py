"""将设备生成剧本的归属从设备调整为宝宝。

Revision ID: 20260924_01
Revises: 20260921_02
Create Date: 2026-09-24
"""

from alembic import op
import sqlalchemy as sa

revision = '20260924_01'
down_revision = '20260921_02'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'u_script',
        sa.Column('baby_id', sa.BigInteger(), nullable=True, comment='宝宝 ID，NULL 表示平台剧本'),
    )

    script = sa.table(
        'u_script',
        sa.column('device_id', sa.Integer()),
        sa.column('baby_id', sa.BigInteger()),
    )
    baby = sa.table(
        'u_baby',
        sa.column('id', sa.BigInteger()),
        sa.column('device_id', sa.BigInteger()),
    )
    op.execute(
        sa.update(script)
        .where(script.c.device_id > 0)
        .values(
            baby_id=sa.select(baby.c.id)
            .where(baby.c.device_id == script.c.device_id)
            .limit(1)
            .scalar_subquery()
        )
    )

    op.create_foreign_key(
        'fk_script_baby_id',
        'u_script',
        'u_baby',
        ['baby_id'],
        ['id'],
        ondelete='RESTRICT',
    )
    op.create_index('ix_u_script_baby_id', 'u_script', ['baby_id'])
    op.drop_index('ix_u_script_device_id', table_name='u_script')
    op.drop_column('u_script', 'device_id')


def downgrade() -> None:
    op.add_column(
        'u_script',
        sa.Column(
            'device_id',
            sa.Integer(),
            nullable=False,
            server_default='0',
            comment='设备 ID，0 表示平台',
        ),
    )

    script = sa.table(
        'u_script',
        sa.column('device_id', sa.Integer()),
        sa.column('baby_id', sa.BigInteger()),
    )
    baby = sa.table(
        'u_baby',
        sa.column('id', sa.BigInteger()),
        sa.column('device_id', sa.BigInteger()),
    )
    op.execute(
        sa.update(script)
        .where(script.c.baby_id.is_not(None))
        .values(
            device_id=sa.func.coalesce(
                sa.select(baby.c.device_id)
                .where(baby.c.id == script.c.baby_id)
                .limit(1)
                .scalar_subquery(),
                0,
            )
        )
    )

    op.create_index('ix_u_script_device_id', 'u_script', ['device_id'])
    op.drop_constraint('fk_script_baby_id', 'u_script', type_='foreignkey')
    op.drop_index('ix_u_script_baby_id', table_name='u_script')
    op.drop_column('u_script', 'baby_id')
    op.alter_column('u_script', 'device_id', existing_type=sa.Integer(), server_default=None)
