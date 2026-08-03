# -*- coding: UTF-8 -*-
"""
Cloud script table.
"""

from typing import Any

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class CloudScript(Base):
    """Cloud script table."""

    __tablename__ = 'u_cloud_script'

    id: Mapped[id_key] = mapped_column(init=False)
    title: Mapped[str] = mapped_column(sa.String(256), index=True, comment='Title')
    summary: Mapped[str | None] = mapped_column(sa.String(1000), comment='Summary')
    cover_url: Mapped[str | None] = mapped_column(sa.String(512), comment='Cover URL')
    author: Mapped[str | None] = mapped_column(sa.String(128), index=True, comment='Author')
    toy_ids: Mapped[list[int]] = mapped_column(sa.JSON, comment='Toy ID list')
    content: Mapped[list[dict[str, Any]]] = mapped_column(sa.JSON, comment='Script line content')
    device_id: Mapped[int] = mapped_column(default=0, index=True, comment='Device ID, 0 means platform')
    favorite: Mapped[int] = mapped_column(default=0, comment='Favorite flag (0 no, 1 yes)')
    version: Mapped[int] = mapped_column(default=1, comment='Version')
    status: Mapped[int] = mapped_column(default=0, index=True, comment='Status (0 disabled, 1 enabled)')
    remark: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='Remark')
