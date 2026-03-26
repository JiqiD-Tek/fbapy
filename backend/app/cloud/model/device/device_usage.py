# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : device_usage.py
@Author  : guhua@jiqid.com
@Date    : 2026/01/26 15:40
"""

import enum

from datetime import datetime

import sqlalchemy as sa

from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, id_key
from backend.utils.timezone import timezone


class UsageStatus(enum.Enum):
    """使用记录状态"""

    ACTIVE = 'ACTIVE'  # 使用中
    COMPLETED = 'COMPLETED'  # 正常结束并扣费
    FAILED = 'FAILED'  # 失败（余额不足等）
    CANCELLED = 'CANCELLED'  # 已取消


class DeviceUsage(Base):
    """设备使用额度表"""

    __tablename__ = 'u_device_usage'

    id: Mapped[id_key] = mapped_column(init=False)
    did: Mapped[str] = mapped_column(sa.String(64), index=True, comment='设备编码')

    # 使用时间信息
    start_time: Mapped[datetime] = mapped_column(TimeZone, default_factory=timezone.now, comment='开始使用时间')
    end_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='结束使用时间')
    apply_quota: Mapped[int] = mapped_column(sa.Integer, default=0, comment='申请使用时长（秒）')
    actual_quota: Mapped[int] = mapped_column(sa.Integer, default=0, comment='实际使用时长（秒）')

    # 状态信息
    status: Mapped[UsageStatus] = mapped_column(SQLEnum(UsageStatus), default=UsageStatus.ACTIVE, comment='使用状态')

    # 业务信息
    remark: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='备注')
