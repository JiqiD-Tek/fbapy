# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : album_service.py
@Author  : OpenAI
@Date    : 2026/03/26
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.iot.crud.cloud.crud_album import cloud_album_dao
from backend.app.iot.crud.cloud.crud_song import cloud_song_dao
from backend.app.iot.model import CloudAlbum
from backend.app.iot.schema.cloud.album import ContentType, CreateAlbumParam, UpdateAlbumParam
from backend.common.exception import errors
from backend.common.pagination import paging_data


class CloudAlbumService:
    @staticmethod
    async def get_album(*, db: AsyncSession, pk: int) -> CloudAlbum:
        album = await cloud_album_dao.get(db, pk)
        if not album:
            raise errors.NotFoundError(msg='专辑不存在')
        return album

    @staticmethod
    async def get_album_list(
        *,
        db: AsyncSession,
        title: str | None = None,
        content_type: ContentType | None = None,
        status: int | None = None,
    ) -> dict[str, Any]:
        album_select = await cloud_album_dao.get_select(
            title=title,
            content_type=content_type,
            status=status,
        )
        return await paging_data(db, album_select)

    @staticmethod
    async def create_album(*, db: AsyncSession, obj: CreateAlbumParam) -> CloudAlbum:
        return await cloud_album_dao.create(db, obj)

    @staticmethod
    async def update_album(*, db: AsyncSession, pk: int, obj: UpdateAlbumParam) -> int:
        album = await cloud_album_dao.get(db, pk)
        if not album:
            raise errors.NotFoundError(msg='专辑不存在')

        payload = obj.model_dump(exclude_unset=True)
        if not payload:
            raise errors.RequestError(msg='更新内容不能为空')
        CloudAlbumService._validate_album_payload(payload)

        count = await cloud_album_dao.update(db, pk, obj)
        if count > 0 and 'content_type' in payload and payload['content_type'] != album.content_type:
            await cloud_song_dao.update_content_type_by_album_id(
                db,
                album_id=pk,
                content_type=payload['content_type'],
            )
        return count

    @staticmethod
    async def delete_album(*, db: AsyncSession, pk: int) -> int:
        album = await cloud_album_dao.get(db, pk)
        if not album:
            raise errors.NotFoundError(msg='专辑不存在')

        song_count = await cloud_song_dao.count_by_album_id(db, pk)
        if song_count > 0:
            raise errors.RequestError(msg='专辑下存在歌曲，无法删除')

        return await cloud_album_dao.delete(db, pk)

    @staticmethod
    def _validate_album_payload(payload: dict[str, Any]) -> None:
        if 'title' in payload and payload['title'] is None:
            raise errors.RequestError(msg='专辑标题不能为空')
        if 'content_type' in payload and payload['content_type'] is None:
            raise errors.RequestError(msg='内容类型不能为空')


cloud_album_service: CloudAlbumService = CloudAlbumService()
