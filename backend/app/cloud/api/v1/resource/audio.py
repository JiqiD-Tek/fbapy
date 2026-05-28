# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : audio.py
@Author  : OpenAI
@Date    : 2026/03/25
"""

from typing import Annotated

from fastapi import APIRouter, Path, Query

from backend.app.cloud.schema.resource.album import (
    ContentType,
    CreateAlbumParam,
    GetAlbumDetail,
    UpdateAlbumParam,
)
from backend.app.cloud.schema.resource.song import (
    CreateSongParam,
    GetSongDetail,
    UpdateSongParam,
)
from backend.app.cloud.service.resource.album_service import cloud_album_service
from backend.app.cloud.service.resource.song_service import cloud_song_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.auth import DependsDeviceOrJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/albums/{pk}', summary='获取专辑详情', dependencies=[DependsJwtAuth])
async def get_album(
        db: CurrentSession,
        pk: Annotated[int, Path(description='专辑 ID')],
) -> ResponseSchemaModel[GetAlbumDetail]:
    data = await cloud_album_service.get_album(db=db, pk=pk)
    return response_base.success(data=data)


@router.get('/albums', summary='分页获取专辑列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_album_paginated(
        db: CurrentSession,
        title: Annotated[str | None, Query(description='专辑标题')] = None,
        content_type: Annotated[ContentType | None, Query(description='内容类型：1儿歌 2故事 3哄睡')] = None,
        status: Annotated[int | None, Query(description='状态')] = None,
        column: Annotated[str | None, Query(description='排序字段')] = 'id',
        order: Annotated[str | None, Query(description='排序方式')] = 'desc',
) -> ResponseSchemaModel[PageData[GetAlbumDetail]]:
    page_data = await cloud_album_service.get_album_list(
        db=db,
        title=title,
        content_type=content_type,
        status=status,
        column=column,
        order=order,
    )
    return response_base.success(data=page_data)


@router.post('/albums', summary='创建专辑', dependencies=[DependsJwtAuth])
async def create_album(
        db: CurrentSessionTransaction,
        obj: CreateAlbumParam,
) -> ResponseSchemaModel[GetAlbumDetail]:
    album = await cloud_album_service.create_album(db=db, obj=obj)
    return response_base.success(data=album)


@router.put('/albums/{pk}', summary='更新专辑', dependencies=[DependsJwtAuth])
async def update_album(
        db: CurrentSessionTransaction,
        pk: Annotated[int, Path(description='专辑 ID')],
        obj: UpdateAlbumParam,
) -> ResponseModel:
    count = await cloud_album_service.update_album(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/albums/{pk}', summary='删除专辑', dependencies=[DependsJwtAuth])
async def delete_album(
        db: CurrentSessionTransaction,
        pk: Annotated[int, Path(description='专辑 ID')],
) -> ResponseModel:
    count = await cloud_album_service.delete_album(db=db, pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.get('/songs/{pk}', summary='获取歌曲详情', dependencies=[DependsDeviceOrJwtAuth])
async def get_song(
        db: CurrentSession,
        pk: Annotated[int, Path(description='歌曲 ID')],
) -> ResponseSchemaModel[GetSongDetail]:
    data = await cloud_song_service.get_song(db=db, pk=pk)
    return response_base.success(data=data)


@router.get('/songs', summary='分页获取歌曲列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_song_paginated(
        db: CurrentSession,
        title: Annotated[str | None, Query(description='歌曲标题')] = None,
        album_id: Annotated[int | None, Query(description='本地专辑 ID')] = None,
        content_type: Annotated[ContentType | None, Query(description='内容类型：1儿歌 2故事 3哄睡')] = None,
        status: Annotated[int | None, Query(description='状态')] = None,
) -> ResponseSchemaModel[PageData[GetSongDetail]]:
    page_data = await cloud_song_service.get_song_list(
        db=db,
        title=title,
        album_id=album_id,
        content_type=content_type,
        status=status,
    )
    return response_base.success(data=page_data)


@router.post('/songs', summary='创建歌曲', dependencies=[DependsJwtAuth])
async def create_song(
        db: CurrentSessionTransaction,
        obj: CreateSongParam,
) -> ResponseSchemaModel[GetSongDetail]:
    song = await cloud_song_service.create_song(db=db, obj=obj)
    return response_base.success(data=song)


@router.put('/songs/{pk}', summary='更新歌曲', dependencies=[DependsJwtAuth])
async def update_song(
        db: CurrentSessionTransaction,
        pk: Annotated[int, Path(description='歌曲 ID')],
        obj: UpdateSongParam,
) -> ResponseModel:
    count = await cloud_song_service.update_song(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/songs/{pk}', summary='删除歌曲', dependencies=[DependsJwtAuth])
async def delete_song(
        db: CurrentSessionTransaction,
        pk: Annotated[int, Path(description='歌曲 ID')],
) -> ResponseModel:
    count = await cloud_song_service.delete_song(db=db, pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()
