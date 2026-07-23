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

from backend.common.model import Base, DataClassBase, TimeZone, id_key
from backend.utils.timezone import timezone


class BillAccount(Base):
    """计费账户。"""

    __tablename__ = 'u_bill_account'
    __table_args__ = (
        sa.UniqueConstraint('subject_type', 'subject_key', name='uk_subject'),
        {'comment': '计费账户'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    subject_type: Mapped[str] = mapped_column(sa.String(16), comment='主体类型，当前固定 DEVICE')
    subject_key: Mapped[str] = mapped_column(sa.String(64), comment='主体标识，当前为 device DID')
    balance_token: Mapped[int] = mapped_column(sa.BigInteger, default=0, comment='当前余额快照，单位 token')
    status: Mapped[str] = mapped_column(sa.String(16), default='ACTIVE', comment='ACTIVE / BLOCKED')


class BillTxn(DataClassBase):
    """账务流水。流水是不可变事实表，只保留 created_time。"""

    __tablename__ = 'u_bill_txn'
    __table_args__ = (
        sa.UniqueConstraint('session_id', 'sentence_id', name='uk_txn_sentence'),
        sa.Index('idx_account_created_time', 'account_id', 'created_time'),
        sa.Index('idx_session_created_time', 'session_id', 'created_time'),
        {'comment': '账务流水'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    account_id: Mapped[int] = mapped_column(sa.BigInteger, comment='所属计费账户 ID')
    session_id: Mapped[str] = mapped_column(sa.String(64), comment='来源连接级 session_id')
    sentence_id: Mapped[str] = mapped_column(sa.String(64), comment='来源轮次级 sentence_id')
    amount_token: Mapped[int] = mapped_column(sa.BigInteger, comment='本次变动金额，统一为正数')
    balance_token: Mapped[int] = mapped_column(sa.BigInteger, comment='本次变动后的余额快照')
    change_type: Mapped[str] = mapped_column(
        sa.String(16), default='DEBIT', server_default='DEBIT', comment='变动类型，当前主路径固定为 DEBIT',
    )
    created_time: Mapped[datetime] = mapped_column(
        TimeZone,
        init=False,
        default_factory=timezone.now,
        comment='创建时间',
    )
