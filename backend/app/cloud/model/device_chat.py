# -*- coding: UTF-8 -*-
"""
Device chat table.
"""

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UniversalText, id_key


class DeviceChat(Base):
    """设备聊天记录表"""

    __tablename__ = 'u_device_chat'
    __table_args__ = (
        sa.Index('idx_device_chat_device_time', 'device_id', 'created_time'),
        sa.Index('idx_device_chat_device_toy_time', 'device_id', 'toy_id', 'created_time'),
        sa.Index('idx_device_chat_user_time', 'user_id', 'created_time'),
        sa.Index('idx_device_chat_baby_time', 'baby_id', 'created_time'),
        {'comment': '设备聊天记录表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    device_id: Mapped[int] = mapped_column(sa.BigInteger, comment='设备ID')
    toy_id: Mapped[int] = mapped_column(sa.BigInteger, comment='玩偶ID')
    user_message: Mapped[str] = mapped_column(UniversalText, comment='用户消息内容')
    reply_message: Mapped[str] = mapped_column(UniversalText, comment='回复内容')
    user_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='用户ID')
    baby_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='宝宝ID')
