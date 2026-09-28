# -*- coding: UTF-8 -*-
"""首页配置模型。"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class Homepage(Base):
    """首页配置表，保存首页各区域的配置数组。"""

    __tablename__ = 'u_homepage'
    __table_args__ = (
        sa.UniqueConstraint('config_type', name='uq_homepage_type'),
        {'comment': '首页配置表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    config_type: Mapped[str] = mapped_column(
        sa.String(32), index=True, comment='配置类型：banner、newest、featured',
    )
    content: Mapped[list[Any]] = mapped_column(
        sa.JSON, default_factory=list, comment='配置内容数组',
    )
