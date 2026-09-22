# -*- coding: UTF-8 -*-
"""商城商品模型。"""

from __future__ import annotations

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UniversalText, id_key


class Product(Base):
    """商城商品表。"""

    __tablename__ = 'u_product'
    __table_args__ = (
        sa.Index('idx_product_parent_status_sort', 'parent_id', 'status', 'sort'),
        sa.Index('idx_product_ref', 'ref_type', 'ref_id'),
        {'comment': '商城商品表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)

    ref_type: Mapped[str] = mapped_column(
        sa.String(32), index=True, comment='关联对象类型：toy_series、toy',
    )
    name: Mapped[str] = mapped_column(sa.String(128), comment='商品名称')
    price: Mapped[int] = mapped_column(sa.BigInteger, comment='商品价格，单位：分')
    ref_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='关联对象 ID，根据关联对象类型确定对象')
    parent_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey('u_product.id', ondelete='RESTRICT'),
        default=None, index=True, comment='父商品 ID，NULL 表示顶级商品',
    )
    cover_url: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='商品封面地址')
    summary: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='商品简介')
    detail: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='商品详情')
    purchase_url: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='外部购买地址')
    status: Mapped[int] = mapped_column(sa.SmallInteger, default=0, index=True, comment='状态：0 草稿，1 上架，2 下架')
    sort: Mapped[int] = mapped_column(default=0, comment='排序值，越小越靠前')
    remark: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='备注')
