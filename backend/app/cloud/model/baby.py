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
    """宝宝表"""

    __tablename__ = 'u_baby'

    id: Mapped[id_key] = mapped_column(init=False)
    name: Mapped[str] = mapped_column(sa.String(64), comment='宝宝姓名')
    user_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='用户 ID')
    device_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, unique=True, comment='设备 ID')
    nickname: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='宝宝昵称')
    avatar: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='头像')
    sex: Mapped[int] = mapped_column(default=0, comment='性别（0 未知，1 男，2 女）')
    birthday: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='生日')
    remark: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='备注')
