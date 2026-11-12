"""Add the TTS resource ID to toys.

Revision ID: 20261112_01
Revises: 20261111_01
"""

import sqlalchemy as sa
from alembic import op

revision = '20261112_01'
down_revision = '20261111_01'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'u_toy',
        sa.Column('resource_id', sa.String(128), nullable=True, comment='火山语音合成资源 ID'),
    )

    toy = sa.table(
        'u_toy',
        sa.column('voice_type', sa.SmallInteger()),
        sa.column('resource_id', sa.String(128)),
    )
    op.execute(
        toy.update()
        .where(toy.c.voice_type.in_([1, 2, 3]))
        .values(
            resource_id=sa.case(
                (toy.c.voice_type == 1, 'seed-tts-2.0'),
                else_='seed-icl-2.0',
            )
        )
    )
    op.drop_column('u_toy', 'voice_type')


def downgrade() -> None:
    op.add_column(
        'u_toy',
        sa.Column(
            'voice_type',
            sa.SmallInteger(),
            nullable=True,
            comment='声音类型：1 公共声音，2 克隆声音，3 自定义声音',
        ),
    )

    toy = sa.table(
        'u_toy',
        sa.column('voice_type', sa.SmallInteger()),
        sa.column('resource_id', sa.String(128)),
    )
    op.execute(
        toy.update()
        .where(toy.c.resource_id.in_(['seed-tts-2.0', 'seed-icl-2.0']))
        .values(
            voice_type=sa.case(
                (toy.c.resource_id == 'seed-tts-2.0', 1),
                else_=2,
            )
        )
    )
    op.drop_column('u_toy', 'resource_id')
