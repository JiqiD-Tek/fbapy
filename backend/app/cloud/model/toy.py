# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : toy.py
@Author  : OpenAI
@Date    : 2026/07/06
"""

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UniversalText, id_key


class ToySeries(Base):
    """云端玩偶系列表。"""

    __tablename__ = 'u_toy_series'
    __table_args__ = (
        sa.Index('idx_status_sort', 'status', 'sort'),
        {'comment': '云端玩偶系列表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)

    name: Mapped[str] = mapped_column(sa.String(64), index=True, comment='玩偶系列名称')
    image_url: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='玩偶系列图片地址')
    description: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='玩偶系列描述')
    status: Mapped[int] = mapped_column(sa.SmallInteger, default=1, index=True, comment='状态：0 禁用，1 启用')
    sort: Mapped[int] = mapped_column(default=0, comment='排序值，越小越靠前')


class Toy(Base):
    """云端玩偶表。"""

    __tablename__ = 'u_toy'
    __table_args__ = (
        sa.Index('idx_status_sort', 'status', 'sort'),
        {'comment': '云端玩偶表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)

    series_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey('u_toy_series.id', ondelete='RESTRICT'),
        default=None, index=True, comment='玩偶系列 ID',
    )
    name: Mapped[str | None] = mapped_column(sa.String(128), default=None, index=True, comment='玩偶名称')
    avatar_url: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='玩偶头像地址')
    summary: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='玩偶简介')
    intro_audio_url: Mapped[str | None] = mapped_column(
        sa.String(512), default=None, comment='玩偶介绍音频地址',
    )
    related_toy_ids: Mapped[list[int] | None] = mapped_column(sa.JSON, default=None, comment='关联玩偶 ID 列表')

    system_prompt: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='系统提示词')

    voice_provider: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='声音服务商')
    voice_id: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='声音 ID')
    voice_type: Mapped[int | None] = mapped_column(
        sa.SmallInteger, default=None, comment='声音类型：1 公共声音，2 克隆声音，3 自定义声音',
    )
    voice_name: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='声音名称')
    voice_language: Mapped[str | None] = mapped_column(
        sa.String(32), default=None, comment='声音语言，例如 zh-CN、en-US、zh-TW',
    )
    speech_rate: Mapped[int] = mapped_column(default=0, comment='语速')
    loudness_rate: Mapped[int] = mapped_column(default=0, comment='音量')

    status: Mapped[int] = mapped_column(sa.SmallInteger, default=1, index=True, comment='状态：0 禁用，1 启用')
    sort: Mapped[int] = mapped_column(default=0, comment='排序值，越小越靠前')
    remark: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='备注')


class ToyNfc(Base):
    """玩偶 NFC 编码绑定表。"""

    __tablename__ = 'u_toy_nfc'
    __table_args__ = (
        sa.UniqueConstraint('nfc_code', name='uq_toy_nfc_code'),
        sa.Index('idx_toy_nfc_toy_id', 'toy_id'),
        sa.Index('idx_toy_nfc_batch_no', 'batch_no'),
        {'comment': '玩偶 NFC 编码绑定表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)

    toy_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey('u_toy.id', ondelete='RESTRICT'), nullable=False, comment='玩偶 ID',
    )
    nfc_code: Mapped[str] = mapped_column(sa.String(64), nullable=False, comment='NFC 编码')
    batch_no: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='NFC 批次号')
    status: Mapped[int] = mapped_column(sa.SmallInteger, default=1, index=True, comment='状态：0 禁用，1 启用')
    remark: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='备注')
