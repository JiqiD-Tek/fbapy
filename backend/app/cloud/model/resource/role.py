# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : role.py
@Author  : OpenAI
@Date    : 2026/07/06
"""

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UniversalText, id_key


class CloudRole(Base):
    """云资源角色表"""

    __tablename__ = 'u_cloud_role'
    __table_args__ = (
        sa.Index('idx_status_sort', 'status', 'sort'),
        {'comment': '云资源角色表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)

    group_key: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='虚拟角色分组标识：小小星球')
    name: Mapped[str | None] = mapped_column(sa.String(128), default=None, index=True, comment='角色名称')
    avatar_url: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='角色头像地址')
    summary: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='角色简介')

    system_prompt: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='系统提示词')

    voice_provider: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='音色提供方')
    voice_id: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='音色 ID')
    voice_type: Mapped[int | None] = mapped_column(
        sa.SmallInteger, default=None, comment='音色类型：1官方音色 2复刻音色 3自定义音色',
    )
    voice_name: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='音色名称')
    voice_language: Mapped[str | None] = mapped_column(
        sa.String(32), default=None, comment='音色语言，如 zh-CN、en-US、zh-TW',
    )

    status: Mapped[int] = mapped_column(sa.SmallInteger, default=1, index=True, comment='状态：0禁用 1启用')
    sort: Mapped[int] = mapped_column(default=0, comment='排序值，越小越靠前')
    remark: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='备注')
