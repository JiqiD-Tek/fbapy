# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : device.py
@Author  : guhua@jiqid.com
@Date    : 2025/11/25 10:41
"""
import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class Device(Base):
    """设备表"""

    __tablename__ = 'u_device'

    id: Mapped[id_key] = mapped_column(init=False)
    did: Mapped[str] = mapped_column(sa.String(64), unique=True, index=True, comment='设备编码')
    sn: Mapped[str] = mapped_column(sa.String(64), unique=True, comment='设备序列号')
    mac: Mapped[str] = mapped_column(sa.String(64), unique=True, comment='设备MAC地址')
    model: Mapped[str] = mapped_column(sa.String(64), comment='设备型号')

    name: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='设备名称')
    firmware: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='固件版本')
    hardware: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='硬件版本')
    user_id: Mapped[int | None] = mapped_column(sa.Integer, default=None, comment='设备所有者ID')
