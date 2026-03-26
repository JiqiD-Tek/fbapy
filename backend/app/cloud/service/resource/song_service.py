# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : song_service.py
@Author  : OpenAI
@Date    : 2026/03/26
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.cloud.crud.resource.crud_album import cloud_album_dao
from backend.app.cloud.crud.resource.crud_song import cloud_song_dao
from backend.app.cloud.model import CloudSong
from backend.app.cloud.schema.resource.album import ContentType
from backend.app.cloud.schema.resource.song import CreateSongParam, UpdateSongParam
from backend.common.exception import errors
from backend.common.pagination import paging_data


class CloudSongService:
    @staticmethod
    async def get_song(*, db: AsyncSession, pk: int) -> CloudSong:
        song = await cloud_song_dao.get(db, pk)
        if not song:
            raise errors.NotFoundError(msg='歌曲不存在')
        return song

    @staticmethod
    async def get_song_list(
        *,
        db: AsyncSession,
        title: str | None = None,
        album_id: int | None = None,
        content_type: ContentType | None = None,
        status: int | None = None,
    ) -> dict[str, Any]:
        song_select = await cloud_song_dao.get_select(
            title=title,
            album_id=album_id,
            content_type=content_type,
            status=status,
        )
        return await paging_data(db, song_select)

    async def create_song(self, *, db: AsyncSession, obj: CreateSongParam) -> CloudSong:
        payload = obj
        if obj.album_id is not None:
            payload = await self._normalize_song_with_album(db=db, obj=obj)
        elif obj.content_type is None:
            raise errors.RequestError(msg='内容类型不能为空')

        song = await cloud_song_dao.create(db, payload)
        await self._sync_album_track_count(db=db, album_id=song.album_id)
        return song

    async def update_song(self, *, db: AsyncSession, pk: int, obj: UpdateSongParam) -> int:
        song = await cloud_song_dao.get(db, pk)
        if not song:
            raise errors.NotFoundError(msg='歌曲不存在')

        payload = obj.model_dump(exclude_unset=True)
        if not payload:
            raise errors.RequestError(msg='更新内容不能为空')
        self._validate_song_payload(payload)

        if song.album_id is not None and 'album_id' not in payload and 'content_type' in payload:
            raise errors.RequestError(msg='已关联专辑的歌曲不能单独修改类型')

        normalized_obj = obj
        if 'album_id' in payload and obj.album_id is not None:
            normalized_obj = await self._normalize_song_with_album(
                db=db,
                obj=obj,
            )

        old_album_id = song.album_id
        count = await cloud_song_dao.update(db, pk, normalized_obj)
        refreshed = await cloud_song_dao.get(db, pk)
        await self._sync_album_track_count(db=db, album_id=old_album_id)
        await self._sync_album_track_count(db=db, album_id=refreshed.album_id if refreshed else None)
        return count

    async def delete_song(self, *, db: AsyncSession, pk: int) -> int:
        song = await cloud_song_dao.get(db, pk)
        if not song:
            raise errors.NotFoundError(msg='歌曲不存在')

        count = await cloud_song_dao.delete(db, pk)
        await self._sync_album_track_count(db=db, album_id=song.album_id)
        return count

    @staticmethod
    async def _normalize_song_with_album(
        *,
        db: AsyncSession,
        obj: CreateSongParam | UpdateSongParam,
    ) -> CreateSongParam | UpdateSongParam:
        if obj.album_id is None:
            return obj

        album = await cloud_album_dao.get(db, obj.album_id)
        if not album:
            raise errors.NotFoundError(msg='专辑不存在')

        return obj.model_copy(update={'content_type': album.content_type})

    @staticmethod
    async def _sync_album_track_count(*, db: AsyncSession, album_id: int | None) -> None:
        if album_id is None:
            return

        album = await cloud_album_dao.get(db, album_id)
        if not album:
            return

        track_count = await cloud_song_dao.count_by_album_id(db, album_id)
        await cloud_album_dao.update_track_count(db, album_id, track_count)

    @staticmethod
    def _validate_song_payload(payload: dict[str, Any]) -> None:
        if 'title' in payload and payload['title'] is None:
            raise errors.RequestError(msg='歌曲标题不能为空')
        if 'content_type' in payload and payload['content_type'] is None:
            raise errors.RequestError(msg='内容类型不能为空')


cloud_song_service: CloudSongService = CloudSongService()
