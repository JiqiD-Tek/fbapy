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
    did: Mapped[str] = mapped_column(sa.BigInteger, comment='设备did')

    category: Mapped[str | None] = mapped_column(sa.String(256), comment='反馈类型')
    content: Mapped[str | None] = mapped_column(sa.String(1000), default=None, comment='反馈内容')
    pic_url: Mapped[str | None] = mapped_column(sa.String(1000), default=None, comment='反馈图片地址')
    file_url: Mapped[str | None] = mapped_column(sa.String(1000), default=None, comment='反馈日志文件地址')
    contact: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='联系方式')
    comment: Mapped[str | None] = mapped_column(sa.String(1000), default=None, comment='处理备注')
    status: Mapped[int] = mapped_column(default=0, comment='状态(0：不需要日志上传 1：需要日志上传)')
