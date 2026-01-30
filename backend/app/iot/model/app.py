# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : app.py
@Author  : guhua@jiqid.com
@Date    : 2025/11/25 10:41
"""
import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class App(Base):
    """应用表"""

    __tablename__ = 'u_app'

    id: Mapped[id_key] = mapped_column(init=False)
    name: Mapped[str] = mapped_column(sa.String(64), comment='应用名称')
    package_name: Mapped[str] = mapped_column(sa.String(64), comment='应用包名')
    size: Mapped[int] = mapped_column(comment='应用包大小')
    md5: Mapped[str] = mapped_column(sa.String(32), comment='应用包MD5')
    version: Mapped[str] = mapped_column(sa.String(64), comment='应用版本')

    icon: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='应用图标')
    description: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='应用描述')
    download_url: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='应用下载地址')
    status: Mapped[int] = mapped_column(default=0, comment='状态(0禁用 1启用)')
    remark: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='备注')
