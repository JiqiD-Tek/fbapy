# -*- coding: UTF-8 -*-
"""剧本模型。"""

from typing import Any

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class Script(Base):
    """剧本表。"""

    __tablename__ = 'u_script'
    __table_args__ = (sa.Index('idx_script_album_id', 'album_id'), {'comment': '剧本表。'})

    id: Mapped[id_key] = mapped_column(init=False)
    album_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey('u_script_album.id', ondelete='RESTRICT'),
        nullable=True, comment='剧本专辑 ID，NULL 表示不属于专辑',
    )
    # 设备生成剧本时固定归属当前绑定的宝宝；平台剧本不属于宝宝。
    baby_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey('u_baby.id', ondelete='RESTRICT'),
        nullable=True, index=True, comment='宝宝 ID，NULL 表示平台剧本',
    )
    title: Mapped[str] = mapped_column(sa.String(256), index=True, comment='剧本标题')
    content_types: Mapped[list[int] | None] = mapped_column(
        sa.JSON, comment='内容类型列表（1语言 2科学 3社会 4艺术 5健康）',
    )
    summary: Mapped[str | None] = mapped_column(sa.String(1000), comment='剧本摘要')
    cover_url: Mapped[str | None] = mapped_column(sa.String(512), comment='剧本封面地址')
    author: Mapped[str | None] = mapped_column(sa.String(128), index=True, comment='作者')
    content: Mapped[list[dict[str, Any]]] = mapped_column(sa.JSON, comment='剧本台词内容')
    play_url: Mapped[str | None] = mapped_column(sa.String(1000), default=None, comment='播放地址')
    duration: Mapped[int] = mapped_column(default=0, comment='时长（秒）')
    track_no: Mapped[int] = mapped_column(default=0, comment='专辑内曲目序号')

    favorite: Mapped[int] = mapped_column(
        sa.SmallInteger, default=0, server_default=sa.text('0'), nullable=False, comment='是否收藏：0 否，1 是',
    )
    version: Mapped[int] = mapped_column(default=1, comment='版本号')
    status: Mapped[int] = mapped_column(default=0, index=True, comment='状态：0 草稿，1 启用，2 禁用')
    remark: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='备注')
