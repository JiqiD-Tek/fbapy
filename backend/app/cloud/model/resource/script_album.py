# -*- coding: UTF-8 -*-
"""剧本专辑模型。"""

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UniversalText, id_key


class ScriptAlbum(Base):
    """剧本专辑表。"""

    __tablename__ = 'u_script_album'

    id: Mapped[id_key] = mapped_column(init=False)
    title: Mapped[str] = mapped_column(sa.String(256), index=True, comment='专辑标题')
    toy_ids: Mapped[list[int]] = mapped_column(sa.JSON, comment='专辑适用的玩偶 ID 列表')
    description: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='专辑简介')
    cover_url: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='专辑封面地址')
    author: Mapped[str | None] = mapped_column(sa.String(128), default=None, index=True, comment='作者')
    track_count: Mapped[int] = mapped_column(default=0, comment='剧本数量')
    status: Mapped[int] = mapped_column(default=1, index=True, comment='状态：0 禁用，1 启用')
    remark: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='备注')
