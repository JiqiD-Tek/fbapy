# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : firmware.py
@Author  : OpenAI
@Date    : 2026/03/26
"""

import sqlalchemy as sa

from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, id_key


class Firmware(Base):
    """固件表"""

    __tablename__ = 'u_firmware'

    id: Mapped[id_key] = mapped_column(init=False)
    name: Mapped[str] = mapped_column(sa.String(64), comment='固件名称')
    version: Mapped[str] = mapped_column(sa.String(64), comment='固件版本')
    version_code: Mapped[int] = mapped_column(comment='版本代码')
    size: Mapped[int] = mapped_column(comment='固件大小')
    md5: Mapped[str] = mapped_column(sa.String(32), comment='固件 MD5')
    download_url: Mapped[str] = mapped_column(sa.String(512), comment='固件下载地址')

    download_count: Mapped[int] = mapped_column(default=0, comment='下载次数')
    description: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='固件描述')
    min_version: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='最低兼容版本')
    max_version: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='最高兼容版本')
    device_model: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='适用设备型号')
    release_scope: Mapped[str] = mapped_column(
        sa.String(16), default='public', comment='发布范围 public=公开 whitelist=白名单',
    )
    is_latest: Mapped[bool] = mapped_column(default=False, comment='是否为最新版本')
    is_force: Mapped[bool] = mapped_column(default=False, comment='是否强制更新')
    status: Mapped[int] = mapped_column(default=0, index=True, comment='固件状态(0禁用 1启用)')
    remark: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='备注')


class FirmwareWhitelist(Base):
    """固件白名单表"""

    __tablename__ = 'u_firmware_whitelist'

    id: Mapped[id_key] = mapped_column(init=False)
    firmware_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='固件 ID')
    device_did: Mapped[str] = mapped_column(sa.String(64), unique=True, index=True, comment='设备 DID')
    enabled: Mapped[bool] = mapped_column(default=True, index=True, comment='是否启用')
    allow_downgrade: Mapped[bool] = mapped_column(default=False, comment='是否允许降级到目标固件')
    expires_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='过期时间')
    remark: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='备注')
