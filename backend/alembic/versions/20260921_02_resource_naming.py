"""统一歌曲、剧本资源表命名并增加剧本专辑。

Revision ID: 20260921_02
Revises: 20260921_01
Create Date: 2026-09-21
"""

import json
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision = '20260921_02'
down_revision = '20260921_01'
branch_labels = None
depends_on = None


def _replace_indexes(table_name: str, mappings: list[tuple[str, str, list[str], bool]]) -> None:
    """将旧表名生成的索引名称替换为新名称。"""
    bind = op.get_bind()
    indexes = {item['name'] for item in sa.inspect(bind).get_indexes(table_name)}
    for old_name, new_name, columns, unique in mappings:
        if old_name in indexes:
            op.drop_index(old_name, table_name=table_name)
        if new_name not in indexes:
            op.create_index(new_name, table_name, columns, unique=unique)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if 'u_cloud_album' in tables:
        op.rename_table('u_cloud_album', 'u_song_album')
    if 'u_cloud_song' in tables:
        op.rename_table('u_cloud_song', 'u_song')
    if 'u_cloud_script' in tables:
        op.rename_table('u_cloud_script', 'u_script')

    op.create_table_comment('u_song_album', '歌曲专辑表')
    op.create_table_comment('u_song', '歌曲表')
    op.create_table_comment('u_script', '剧本表')

    _replace_indexes('u_song_album', [
        ('ix_u_cloud_album_id', 'ix_u_song_album_id', ['id'], True),
        ('ix_u_cloud_album_title', 'ix_u_song_album_title', ['title'], False),
        ('ix_u_cloud_album_content_type', 'ix_u_song_album_content_type', ['content_type'], False),
        ('ix_u_cloud_album_status', 'ix_u_song_album_status', ['status'], False),
    ])
    _replace_indexes('u_song', [
        ('ix_u_cloud_song_id', 'ix_u_song_id', ['id'], True),
        ('ix_u_cloud_song_title', 'ix_u_song_title', ['title'], False),
        ('ix_u_cloud_song_content_type', 'ix_u_song_content_type', ['content_type'], False),
        ('ix_u_cloud_song_status', 'ix_u_song_status', ['status'], False),
        ('ix_u_cloud_song_album_id', 'idx_song_album_id', ['album_id'], False),
    ])
    _replace_indexes('u_script', [
        ('ix_u_cloud_script_id', 'ix_u_script_id', ['id'], True),
        ('ix_u_cloud_script_title', 'ix_u_script_title', ['title'], False),
        ('ix_u_cloud_script_author', 'ix_u_script_author', ['author'], False),
        ('ix_u_cloud_script_device_id', 'ix_u_script_device_id', ['device_id'], False),
        ('ix_u_cloud_script_status', 'ix_u_script_status', ['status'], False),
    ])

    op.create_table(
        'u_script_album',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True, nullable=False, comment='主键 ID'),
        sa.Column('title', sa.String(256), nullable=False, comment='专辑标题'),
        sa.Column('toy_ids', sa.JSON(), nullable=False, comment='专辑适用的玩偶 ID 列表'),
        sa.Column('description', sa.Text(), nullable=True, comment='专辑简介'),
        sa.Column('cover_url', sa.String(512), nullable=True, comment='专辑封面地址'),
        sa.Column('author', sa.String(128), nullable=True, comment='作者'),
        sa.Column('track_count', sa.Integer(), nullable=False, comment='剧本数量'),
        sa.Column('status', sa.SmallInteger(), nullable=False, comment='状态：0 禁用，1 启用'),
        sa.Column('remark', sa.String(500), nullable=True, comment='备注'),
        sa.Column('created_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('deleted_time', sa.DateTime(timezone=True), nullable=True),
        comment='剧本专辑表',
    )
    op.create_index('ix_u_script_album_id', 'u_script_album', ['id'], unique=True)
    op.create_index('ix_u_script_album_title', 'u_script_album', ['title'])
    op.create_index('ix_u_script_album_author', 'u_script_album', ['author'])
    op.create_index('ix_u_script_album_status', 'u_script_album', ['status'])
    op.add_column('u_script', sa.Column('album_id', sa.BigInteger(), nullable=True, comment='剧本专辑 ID'))
    op.add_column('u_script', sa.Column('duration', sa.Integer(), nullable=False, server_default='0', comment='时长（秒）'))
    op.add_column(
        'u_script',
        sa.Column('track_no', sa.Integer(), nullable=False, server_default='0', comment='专辑内曲目序号'),
    )
    script_comments = [
        ('title', sa.String(256), False, '剧本标题'),
        ('content_types', sa.JSON(), True, '内容类型列表（1语言 2科学 3社会 4艺术 5健康）'),
        ('summary', sa.String(1000), True, '剧本摘要'),
        ('cover_url', sa.String(512), True, '剧本封面地址'),
        ('author', sa.String(128), True, '作者'),
        ('content', sa.JSON(), False, '剧本台词内容'),
        ('play_url', sa.String(1000), True, '播放地址'),
        ('device_id', sa.Integer(), False, '设备 ID，0 表示平台'),
        ('favorite', sa.SmallInteger(), False, '是否收藏：0 否，1 是'),
        ('version', sa.Integer(), False, '版本号'),
        ('status', sa.Integer(), False, '状态：0 草稿，1 启用，2 禁用'),
        ('remark', sa.String(500), True, '备注'),
    ]
    for column_name, column_type, nullable, comment in script_comments:
        op.alter_column(
            'u_script',
            column_name,
            existing_type=column_type,
            existing_nullable=nullable,
            comment=comment,
        )

    script_album = sa.table(
        'u_script_album',
        sa.column('id', sa.BigInteger()),
        sa.column('title', sa.String(256)),
        sa.column('toy_ids', sa.JSON()),
        sa.column('track_count', sa.Integer()),
        sa.column('status', sa.SmallInteger()),
        sa.column('created_time', sa.DateTime(timezone=True)),
        sa.column('deleted', sa.BigInteger()),
    )
    rows = bind.execute(sa.text('SELECT id, toy_ids FROM u_script ORDER BY id')).mappings().all()
    groups: dict[tuple[int, ...], int] = {}
    for row in rows:
        value = row['toy_ids'] or []
        if isinstance(value, str):
            value = json.loads(value)
        key = tuple(sorted({int(item) for item in value}))
        if key not in groups:
            result = bind.execute(
                sa.insert(script_album).values(
                    title=f'历史剧本专辑 {len(groups) + 1}',
                    toy_ids=list(key),
                    track_count=0,
                    status=1,
                    created_time=datetime.now(timezone.utc),
                    deleted=0,
                )
            )
            album_id = int(result.inserted_primary_key[0])
            groups[key] = album_id
        bind.execute(
            sa.text('UPDATE u_script SET album_id=:album_id WHERE id=:id'),
            {'album_id': groups[key], 'id': row['id']},
        )

    for album_id in groups.values():
        count = bind.execute(
            sa.text('SELECT COUNT(*) FROM u_script WHERE album_id=:album_id AND deleted=0'), {'album_id': album_id}
        ).scalar_one()
        bind.execute(
            sa.update(script_album).where(script_album.c.id == album_id).values(track_count=count)
        )

    op.alter_column('u_script', 'album_id', existing_type=sa.BigInteger(), nullable=False)
    op.alter_column('u_script', 'duration', existing_type=sa.Integer(), server_default=None)
    op.alter_column('u_script', 'track_no', existing_type=sa.Integer(), server_default=None)
    op.drop_column('u_script', 'toy_ids')
    op.create_foreign_key('fk_script_album_id', 'u_script', 'u_script_album', ['album_id'], ['id'], ondelete='RESTRICT')
    op.create_index('idx_script_album_id', 'u_script', ['album_id'])
    song = sa.table('u_song', sa.column('album_id', sa.BigInteger()))
    song_album = sa.table('u_song_album', sa.column('id', sa.BigInteger()))
    bind.execute(
        sa.update(song).where(
            song.c.album_id.is_not(None),
            ~sa.exists(sa.select(song_album.c.id).where(song_album.c.id == song.c.album_id)),
        ).values(album_id=None)
    )
    op.create_foreign_key('fk_song_album_id', 'u_song', 'u_song_album', ['album_id'], ['id'], ondelete='RESTRICT')


def downgrade() -> None:
    op.add_column('u_script', sa.Column('toy_ids', sa.JSON(), nullable=True, comment='历史玩偶 ID 列表'))
    script_album = sa.table(
        'u_script_album', sa.column('id', sa.BigInteger()), sa.column('toy_ids', sa.JSON()),
    )
    script = sa.table(
        'u_script', sa.column('album_id', sa.BigInteger()), sa.column('toy_ids', sa.JSON()),
    )
    op.execute(
        sa.update(script).values(
            toy_ids=sa.select(script_album.c.toy_ids).where(script_album.c.id == script.c.album_id).scalar_subquery()
        )
    )
    op.alter_column('u_script', 'toy_ids', existing_type=sa.JSON(), nullable=False)
    op.drop_constraint('fk_song_album_id', 'u_song', type_='foreignkey')
    op.drop_constraint('fk_script_album_id', 'u_script', type_='foreignkey')
    op.drop_index('idx_script_album_id', table_name='u_script')
    op.drop_column('u_script', 'album_id')
    op.drop_column('u_script', 'duration')
    op.drop_column('u_script', 'track_no')
    op.drop_index('ix_u_script_album_status', table_name='u_script_album')
    op.drop_index('ix_u_script_album_author', table_name='u_script_album')
    op.drop_index('ix_u_script_album_title', table_name='u_script_album')
    op.drop_index('ix_u_script_album_id', table_name='u_script_album')
    op.drop_table('u_script_album')
    _replace_indexes('u_script', [
        ('ix_u_script_id', 'ix_u_cloud_script_id', ['id'], True),
        ('ix_u_script_title', 'ix_u_cloud_script_title', ['title'], False),
        ('ix_u_script_author', 'ix_u_cloud_script_author', ['author'], False),
        ('ix_u_script_device_id', 'ix_u_cloud_script_device_id', ['device_id'], False),
        ('ix_u_script_status', 'ix_u_cloud_script_status', ['status'], False),
    ])
    _replace_indexes('u_song', [
        ('ix_u_song_id', 'ix_u_cloud_song_id', ['id'], True),
        ('ix_u_song_title', 'ix_u_cloud_song_title', ['title'], False),
        ('ix_u_song_content_type', 'ix_u_cloud_song_content_type', ['content_type'], False),
        ('ix_u_song_status', 'ix_u_cloud_song_status', ['status'], False),
        ('idx_song_album_id', 'ix_u_cloud_song_album_id', ['album_id'], False),
    ])
    _replace_indexes('u_song_album', [
        ('ix_u_song_album_id', 'ix_u_cloud_album_id', ['id'], True),
        ('ix_u_song_album_title', 'ix_u_cloud_album_title', ['title'], False),
        ('ix_u_song_album_content_type', 'ix_u_cloud_album_content_type', ['content_type'], False),
        ('ix_u_song_album_status', 'ix_u_cloud_album_status', ['status'], False),
    ])
    op.create_table_comment('u_script', '云端剧本表')
    op.create_table_comment('u_song', '云资源歌曲表')
    op.create_table_comment('u_song_album', '云资源专辑表')
    op.rename_table('u_script', 'u_cloud_script')
    op.rename_table('u_song', 'u_cloud_song')
    op.rename_table('u_song_album', 'u_cloud_album')
