# -*- coding: UTF-8 -*-
"""设备每日使用量和幂等事件模型。"""

from datetime import date

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class DeviceUsage(Base):
    """设备每日 AI 使用量汇总。"""

    __tablename__ = 'u_device_usage'
    __table_args__ = (
        sa.UniqueConstraint('did', 'usage_date', name='uq_device_usage_did_date'),
        sa.Index('idx_device_usage_date', 'usage_date'),
        {'comment': '设备每日 AI 使用量汇总'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    did: Mapped[str] = mapped_column(sa.String(64), comment='设备 DID')
    usage_date: Mapped[date] = mapped_column(sa.Date, comment='业务日期')
    chat_seconds: Mapped[int] = mapped_column(sa.BigInteger, default=0, comment='AI 对话时长，单位秒')
    story_count: Mapped[int] = mapped_column(sa.BigInteger, default=0, comment='AI 故事创建次数')


class DeviceUsageEvent(Base):
    """设备使用事件幂等记录。"""

    __tablename__ = 'u_device_usage_event'
    __table_args__ = (
        sa.UniqueConstraint('event_type', 'event_key', name='uq_device_usage_event_business'),
        sa.Index('idx_device_usage_event_did_time', 'did', 'created_time'),
        {'comment': '设备使用事件幂等记录'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    did: Mapped[str] = mapped_column(sa.String(64), comment='设备 DID')
    usage_date: Mapped[date] = mapped_column(sa.Date, comment='业务日期')
    event_type: Mapped[str] = mapped_column(sa.String(16), comment='事件类型：CHAT、STORY')
    event_key: Mapped[str] = mapped_column(sa.String(256), comment='事件幂等标识')
    quantity: Mapped[int] = mapped_column(sa.BigInteger, comment='本次使用量：CHAT 单位为秒，STORY 单位为次')
