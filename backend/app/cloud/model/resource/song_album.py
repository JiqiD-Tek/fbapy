# -*- coding: UTF-8 -*-
"""歌曲专辑模型。"""

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UniversalText, id_key


class SongAlbum(Base):
    """歌曲专辑表。"""

    __tablename__ = 'u_song_album'

    id: Mapped[id_key] = mapped_column(init=False)
    title: Mapped[str] = mapped_column(sa.String(256), index=True, comment='专辑标题')
    content_type: Mapped[int] = mapped_column(
        sa.SmallInteger, index=True, comment='内容类型：1 儿歌，2 故事，3 哄睡',
    )
    subtitle: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='专辑副标题')
    cover_url: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='专辑封面地址')
    artist: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='主播名称')
    min_age: Mapped[int | None] = mapped_column(sa.SmallInteger, default=None, comment='最小适龄')
    max_age: Mapped[int | None] = mapped_column(sa.SmallInteger, default=None, comment='最大适龄')
    category_name: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='分类名称')
    tags: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='标签，逗号分隔')
    description: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='专辑简介')
    track_count: Mapped[int] = mapped_column(default=0, comment='歌曲数量')
    status: Mapped[int] = mapped_column(default=1, index=True, comment='状态：0 禁用，1 启用')
    remark: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='备注')
