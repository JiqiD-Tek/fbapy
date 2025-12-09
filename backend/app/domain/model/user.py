# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : auth.py
@Author  : guhua@jiqid.com
@Date    : 2025/11/25 10:41
"""
from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, id_key
from backend.database.db import uuid4_str
from backend.utils.timezone import timezone


class User(Base):
    """用户表"""

    __tablename__ = 'u_user'

    id: Mapped[id_key] = mapped_column(init=False)
    uuid: Mapped[str] = mapped_column(sa.String(64), init=False, default_factory=uuid4_str, unique=True)
    phone: Mapped[str] = mapped_column(sa.String(11), unique=True, index=True, comment='手机号')

    username: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='用户名')
    nickname: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='昵称')
    password: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='密码')
    salt: Mapped[bytes | None] = mapped_column(sa.LargeBinary(255), default=None, comment='加密盐')
    email: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='邮箱')
    avatar: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='头像')
    sex: Mapped[int] = mapped_column(default=0, comment='性别(0未知 1男 2女)')
    birthday: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='生日')
    last_login_time: Mapped[datetime | None] = mapped_column(
        TimeZone, init=False, onupdate=timezone.now, comment='上次登录时间'
    )
