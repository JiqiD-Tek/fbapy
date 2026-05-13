# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : song.py
@Author  : OpenAI
@Date    : 2026/03/25
"""

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UniversalText, id_key


class CloudSong(Base):
    """云资源歌曲表"""

    __tablename__ = 'u_cloud_song'

    id: Mapped[id_key] = mapped_column(init=False)
    title: Mapped[str] = mapped_column(sa.String(256), index=True, comment='歌曲标题')
    content_type: Mapped[int] = mapped_column(sa.SmallInteger, index=True, comment='内容类型：1儿歌 2故事 3哄睡')
    album_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, index=True, comment='本地专辑 ID')

    subtitle: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='歌曲副标题')
    cover_url: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='歌曲封面地址')
    play_url: Mapped[str | None] = mapped_column(sa.String(1000), default=None, comment='播放地址')
    artist: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='歌手/主播')
    content: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='歌曲/故事内容')
    duration: Mapped[int] = mapped_column(default=0, comment='时长(秒)')
    track_no: Mapped[int] = mapped_column(default=0, comment='曲目序号')
    status: Mapped[int] = mapped_column(default=1, index=True, comment='状态(0禁用 1启用)')
    remark: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='备注')
