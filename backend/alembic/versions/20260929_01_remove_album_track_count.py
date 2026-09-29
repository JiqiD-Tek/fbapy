"""移除专辑中的冗余曲目数量字段。

Revision ID: 20260929_01
Revises: 20260928_01
Create Date: 2026-09-29
"""

from alembic import op
import sqlalchemy as sa


revision = '20260929_01'
down_revision = '20260928_01'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column('u_script_album', 'track_count')
    op.drop_column('u_song_album', 'track_count')


def downgrade() -> None:
    op.add_column(
        'u_script_album',
        sa.Column('track_count', sa.Integer(), nullable=False, server_default='0', comment='剧本数量'),
    )
    op.add_column(
        'u_song_album',
        sa.Column('track_count', sa.Integer(), nullable=False, server_default='0', comment='歌曲数量'),
    )
    op.alter_column('u_script_album', 'track_count', server_default=None)
    op.alter_column('u_song_album', 'track_count', server_default=None)
