# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : device_recharge.py
@Author  : OpenAI
@Date    : 2026/01/26 15:41
"""

import enum
import sqlalchemy as sa

from sqlalchemy import BigInteger
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class RechargeType(enum.Enum):
    PAYMENT = 'PAYMENT'
    MANUAL = 'MANUAL'
    PROMOTION = 'PROMOTION'


class DeviceRecharge(Base):
    __tablename__ = 'u_device_recharge'

    id: Mapped[id_key] = mapped_column(init=False, primary_key=True)
    device_did: Mapped[str] = mapped_column(sa.String(64), index=True, comment='设备编码')
    amount: Mapped[int] = mapped_column(BigInteger, comment='充值额度')
    price: Mapped[int] = mapped_column(BigInteger, comment='单价')
    quota_before: Mapped[int] = mapped_column(BigInteger, comment='充值前使用时长（秒）')
    quota_after: Mapped[int] = mapped_column(BigInteger, comment='充值后使用时长（秒）')
    recharge_type: Mapped[RechargeType] = mapped_column(
        SQLEnum(RechargeType),
        default=RechargeType.PAYMENT,
        comment='充值类型',
    )
    remark: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='备注')
    extra_data: Mapped[dict | None] = mapped_column(sa.JSON, default=None, comment='扩展数据')
