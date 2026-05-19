# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : song_service.py
@Author  : OpenAI
@Date    : 2026/03/26
"""

from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.cloud.crud.resource.crud_album import cloud_album_dao
from backend.app.cloud.crud.resource.crud_song import cloud_song_dao
from backend.app.cloud.model import CloudAlbum, CloudSong
from backend.app.cloud.schema.resource.album import ContentType
from backend.app.cloud.schema.resource.song import CreateSongParam, UpdateSongParam
from backend.common.exception import errors
from backend.common.pagination import paging_data

if TYPE_CHECKING:
    from backend.app.cloud.schema.resource.ximalaya import XimalayaSearchParam


class CloudSongService:
    SEARCH_LIMIT = 50

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

    @classmethod
    def _normalize_search_keyword(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @classmethod
    def _resolve_search_keyword(cls, obj: XimalayaSearchParam) -> tuple[str, str]:
        for field_name in ('song_name', 'album_name', 'artist', 'query'):
            keyword = cls._normalize_search_keyword(getattr(obj, field_name))
            if keyword is not None:
                return field_name, keyword

        raise errors.RequestError(msg='搜索关键词不能为空')

    @staticmethod
    def _serialize_search_row(row: sa.RowMapping) -> dict[str, Any]:
        return {
            'id': row['id'],
            'name': row['name'],
            'play_url': row['play_url'] or '',
            'duration': int(row['duration'] or 0),
            'content_type': row['content_type'],
            'artist': (row['song_artist'] or row['album_artist'] or '').strip(),
            'album': row['album'] or '',
        }

    async def search_resources(
            self,
            *,
            db: AsyncSession,
            obj: XimalayaSearchParam,
    ) -> list[dict[str, Any]]:
        search_field, keyword = self._resolve_search_keyword(obj)
        keyword_like = f'%{keyword}%'

        song_name_match = CloudSong.title.like(keyword_like)
        album_name_match = CloudAlbum.title.like(keyword_like)
        artist_match = sa.or_(
            CloudSong.artist.like(keyword_like),
            CloudAlbum.artist.like(keyword_like),
        )

        priority_order = sa.case(
            (song_name_match, 0),
            (album_name_match, 1),
            (artist_match, 2),
            else_=3,
        )

        stmt = (
            sa.select(
                CloudSong.id.label('id'),
                CloudSong.title.label('name'),
                CloudSong.play_url.label('play_url'),
                CloudSong.duration.label('duration'),
                CloudSong.content_type.label('content_type'),
                CloudSong.artist.label('song_artist'),
                CloudAlbum.artist.label('album_artist'),
                CloudAlbum.title.label('album'),
            )
            .select_from(CloudSong)
            .outerjoin(CloudAlbum, CloudAlbum.id == CloudSong.album_id)
            .where(CloudSong.status == 1)
        )

        if search_field == 'song_name':
            stmt = stmt.where(song_name_match).order_by(CloudSong.id.desc())
        elif search_field == 'album_name':
            stmt = stmt.where(album_name_match).order_by(CloudSong.id.desc())
        elif search_field == 'artist':
            stmt = stmt.where(artist_match).order_by(CloudSong.id.desc())
        else:
            stmt = stmt.where(sa.or_(song_name_match, album_name_match, artist_match)).order_by(
                priority_order.asc(),
                CloudSong.id.desc(),
            )

        result = await db.execute(stmt.limit(self.SEARCH_LIMIT))
        return [self._serialize_search_row(row) for row in result.mappings().all()]

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
