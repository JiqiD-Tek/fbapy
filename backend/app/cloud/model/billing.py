# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : billing.py
@Author  : guhua@jiqid.com
@Date    : 2026/07/01
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import DataClassBase, DateTimeMixin, TimeZone, id_key
from backend.utils.timezone import timezone


class BillingTimeBase(DataClassBase, DateTimeMixin):
    """带创建时间和更新时间的计费基类。"""

    __abstract__ = True


class BillAccount(BillingTimeBase):
    """计费账户。"""

    __tablename__ = 'u_bill_account'
    __table_args__ = (
        sa.UniqueConstraint('subject_type', 'subject_key', name='uk_subject'),
        {'comment': '计费主体'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    subject_type: Mapped[str] = mapped_column(sa.String(16), comment='USER / DEVICE')
    subject_key: Mapped[str] = mapped_column(sa.String(64), comment='用户 ID 或设备 DID')
    balance_token: Mapped[int] = mapped_column(default=0, comment='当前余额快照，单位 token')
    status: Mapped[str] = mapped_column(sa.String(16), default='ACTIVE', comment='ACTIVE / BLOCKED')


class BillSession(BillingTimeBase):
    """实时计费会话。"""

    __tablename__ = 'u_bill_session'
    __table_args__ = (
        sa.UniqueConstraint('session_id', name='uk_session_id'),
        {'comment': '实时计费会话'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    session_id: Mapped[str] = mapped_column(sa.String(64), comment='xiaozhi-server session_id')
    account_id: Mapped[int] = mapped_column(comment='计费主体 ID')
    device_did: Mapped[str] = mapped_column(sa.String(64), comment='设备 DID')
    started_at: Mapped[datetime] = mapped_column(TimeZone, comment='会话开始时间')
    status: Mapped[str] = mapped_column(sa.String(16), default='OPEN', comment='OPEN / BLOCKED / CLOSED / ABORTED')
    last_activity_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最近活跃时间')
    ended_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='会话结束时间')


class BillTxn(DataClassBase):
    """账务流水。流水是不可变事实表，只保留 created_time。"""

    __tablename__ = 'u_bill_txn'
    __table_args__ = (
        sa.UniqueConstraint('usage_id', name='uk_txn_usage_id'),
        {'comment': '账务流水'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    charge_id: Mapped[str] = mapped_column(sa.String(64), comment='账务业务号，当前 DEBIT 场景等于 usage_id')
    account_id: Mapped[int] = mapped_column(comment='计费主体 ID')
    change_type: Mapped[str] = mapped_column(sa.String(16), comment='DEBIT / RECHARGE / REFUND / ADJUST')
    delta_token: Mapped[int] = mapped_column(comment='余额变动，正数加款，负数扣款')
    balance_after_token: Mapped[int] = mapped_column(comment='变动后余额快照')
    account_status_after: Mapped[str] = mapped_column(sa.String(16), comment='入账后账户状态')
    session_status_after: Mapped[str] = mapped_column(sa.String(16), comment='入账后会话状态')
    usage_id: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='来源 usage ID，DEBIT 场景必填')
    session_id: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='来源会话 ID')
    turn_no: Mapped[int | None] = mapped_column(default=None, comment='来源回合号')
    stage_no: Mapped[int | None] = mapped_column(default=None, comment='来源阶段号')
    usage_kind: Mapped[str | None] = mapped_column(sa.String(16), default=None, comment='ASR / LLM_INPUT / LLM_OUTPUT / TTS')
    usage_token: Mapped[int | None] = mapped_column(default=None, comment='本次 usage 已换算好的 token')
    provider: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='来源 provider')
    occurred_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='发生时间')
    created_time: Mapped[datetime] = mapped_column(
        TimeZone,
        init=False,
        default_factory=timezone.now,
        comment='创建时间',
    )
