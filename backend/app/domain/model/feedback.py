# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : feedback.py
@Author  : guhua@jiqid.com
@Date    : 2025/11/25 10:41
"""

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class Feedback(Base):
    """反馈表"""

    __tablename__ = 'u_feedback'

    id: Mapped[id_key] = mapped_column(init=False)
    device_id: Mapped[int] = mapped_column(sa.BigInteger, comment='设备ID')
    user_id: Mapped[int] = mapped_column(sa.BigInteger, comment='用户ID')

    name: Mapped[str | None] = mapped_column(sa.String(100), comment='反馈名称')
    pic_url: Mapped[str | None] = mapped_column(sa.String(1000), default=None, comment='反馈图片地址')
    file_url: Mapped[str | None] = mapped_column(sa.String(1000), default=None, comment='反馈文件地址')
    content: Mapped[str | None] = mapped_column(sa.String(1000), default=None, comment='反馈内容')
    comment: Mapped[str | None] = mapped_column(sa.String(1000), default=None, comment='处理备注')
    status: Mapped[int] = mapped_column(default=0, comment='状态(0初始化 1设备处理失败 2设备处理完成 3后台处理完成)')
