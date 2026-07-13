# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : role.py
@Author  : OpenAI
@Date    : 2026/07/06
"""

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UniversalText, id_key


class CloudRole(Base):
    """Cloud role table."""

    __tablename__ = 'u_cloud_role'
    __table_args__ = (
        sa.Index('idx_status_sort', 'status', 'sort'),
        {'comment': 'Cloud role table'},
    )

    id: Mapped[id_key] = mapped_column(init=False)

    series_name: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='Toy series name')
    name: Mapped[str | None] = mapped_column(sa.String(128), default=None, index=True, comment='Role name')
    avatar_url: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='Role avatar URL')
    summary: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='Role summary')
    nfc_code: Mapped[str | None] = mapped_column(sa.String(64), default=None, unique=True, index=True, comment='NFC code')

    system_prompt: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='System prompt')

    voice_provider: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='Voice provider')
    voice_id: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='Voice ID')
    voice_type: Mapped[int | None] = mapped_column(
        sa.SmallInteger, default=None, comment='Voice type: 1 public voice, 2 cloned voice, 3 custom voice',
    )
    voice_name: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='Voice name')
    voice_language: Mapped[str | None] = mapped_column(
        sa.String(32), default=None, comment='Voice language, such as zh-CN, en-US, zh-TW',
    )

    status: Mapped[int] = mapped_column(sa.SmallInteger, default=1, index=True, comment='Status: 0 disabled, 1 enabled')
    sort: Mapped[int] = mapped_column(default=0, comment='Sort value, lower comes first')
    remark: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='Remark')
