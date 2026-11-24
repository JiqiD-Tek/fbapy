"""Replace the toy introduction audio URL with opening audio URLs.

Revision ID: 20261124_02
Revises: 20261124_01
"""

import sqlalchemy as sa

from alembic import op

revision = '20261124_02'
down_revision = '20261124_01'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'u_toy',
        sa.Column('opening_audio_urls', sa.JSON(), nullable=True, comment='玩偶开场白音频地址列表'),
    )
    toy = sa.table(
        'u_toy',
        sa.column('intro_audio_url', sa.String(512)),
        sa.column('opening_audio_urls', sa.JSON()),
    )
    json_array = sa.func.json_build_array if op.get_bind().dialect.name == 'postgresql' else sa.func.JSON_ARRAY
    op.execute(
        toy.update()
        .where(toy.c.intro_audio_url.is_not(None))
        .values(opening_audio_urls=json_array(toy.c.intro_audio_url))
    )
    op.drop_column('u_toy', 'intro_audio_url')


def downgrade() -> None:
    """Restore the single audio URL, keeping the first URL from each array."""
    op.add_column(
        'u_toy',
        sa.Column('intro_audio_url', sa.String(512), nullable=True, comment='玩偶介绍音频地址'),
    )
    toy = sa.table(
        'u_toy',
        sa.column('intro_audio_url', sa.String(512)),
        sa.column('opening_audio_urls', sa.JSON()),
    )
    op.execute(toy.update().values(intro_audio_url=toy.c.opening_audio_urls[0].as_string()))
    op.drop_column('u_toy', 'opening_audio_urls')
