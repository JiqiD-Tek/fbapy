# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : __init__.py
@Author  : OpenAI
@Date    : 2026/03/25
"""

from backend.app.iot.schema.cloud.album import (
    AlbumSchemaBase as AlbumSchemaBase,
    ContentType as ContentType,
    CreateAlbumParam as CreateAlbumParam,
    GetAlbumDetail as GetAlbumDetail,
    UpdateAlbumParam as UpdateAlbumParam,
)
from backend.app.iot.schema.cloud.song import (
    CreateSongParam as CreateSongParam,
    GetSongDetail as GetSongDetail,
    SongSchemaBase as SongSchemaBase,
    UpdateSongParam as UpdateSongParam,
)
