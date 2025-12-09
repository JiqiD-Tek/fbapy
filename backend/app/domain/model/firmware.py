# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : firmware.py
@Author  : guhua@jiqid.com
@Date    : 2025/11/25 10:41
"""

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class Firmware(Base):
    """固件表"""

    __tablename__ = 'u_firmware'

    id: Mapped[id_key] = mapped_column(init=False)
    name: Mapped[str] = mapped_column(sa.String(64), comment='固件名称')
    version: Mapped[str] = mapped_column(sa.String(64), comment='固件版本')
    version_code: Mapped[int] = mapped_column(comment='版本代码')
    size: Mapped[int] = mapped_column(comment='固件大小')
    md5: Mapped[str] = mapped_column(sa.String(32), comment='固件MD5')
    download_url: Mapped[str] = mapped_column(sa.String(512), comment='固件下载地址')

    download_count: Mapped[int] = mapped_column(default=0, comment='下载次数')
    description: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='固件描述')
    min_version: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='最低兼容版本')
    max_version: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='最高兼容版本')
    device_model: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='适用设备型号')
    is_latest: Mapped[bool] = mapped_column(default=False, comment='是否为最新版本')
    is_force: Mapped[bool] = mapped_column(default=False, comment='是否强制更新')
    status: Mapped[int] = mapped_column(default=0, comment='固件状态(0禁用 1启用)')
    remark: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='备注')
