# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : firmware_whitelist.py
@Author  : OpenAI
@Date    : 2026/05/20
"""

import sqlalchemy as sa

from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, id_key


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
