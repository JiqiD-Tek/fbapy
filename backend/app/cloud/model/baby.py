# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : baby.py
@Author  : OpenAI
@Date    : 2026/04/17
"""

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, id_key


class Baby(Base):
    """Baby table"""

    __tablename__ = 'u_baby'

    id: Mapped[id_key] = mapped_column(init=False)
    name: Mapped[str] = mapped_column(sa.String(64), comment='Baby name')
    user_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='User ID')
    device_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, index=True, comment='Device ID')
    nickname: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='Baby nickname')
    avatar: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='Avatar')
    sex: Mapped[int] = mapped_column(default=0, comment='Sex (0 unknown, 1 male, 2 female)')
    birthday: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='Birthday')
    remark: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='Remark')
