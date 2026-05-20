# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : device_usage.py
@Author  : OpenAI
@Date    : 2026/01/26 15:40
"""

import enum
import sqlalchemy as sa

from datetime import datetime

from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, id_key
from backend.utils.timezone import timezone


class UsageStatus(enum.Enum):
    ACTIVE = 'ACTIVE'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    CANCELLED = 'CANCELLED'


class DeviceUsage(Base):
    __tablename__ = 'u_device_usage'

    id: Mapped[id_key] = mapped_column(init=False)
    device_did: Mapped[str] = mapped_column(sa.String(64), index=True, comment='设备编码')
    start_time: Mapped[datetime] = mapped_column(TimeZone, default_factory=timezone.now, comment='开始使用时间')
    end_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='结束使用时间')
    apply_quota: Mapped[int] = mapped_column(sa.Integer, default=0, comment='申请使用时长（秒）')
    actual_quota: Mapped[int] = mapped_column(sa.Integer, default=0, comment='实际使用时长（秒）')
    status: Mapped[UsageStatus] = mapped_column(SQLEnum(UsageStatus), default=UsageStatus.ACTIVE, comment='使用状态')
    remark: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='备注')
