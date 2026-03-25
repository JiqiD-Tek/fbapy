# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : ximalaya.py
@Author  : OpenAI
@Date    : 2026/03/25
"""

from typing import Annotated

from fastapi import APIRouter, Query

from backend.app.iot.schema.ximalaya import (
    XimalayaBrowseAlbumParam,
    XimalayaEndpointInvokeParam,
    XimalayaListAlbumsParam,
    XimalayaListCategoriesParam,
    XimalayaListTagsParam,
    XimalayaPathInvokeParam,
    XimalayaSearchAlbumsParam,
    XimalayaSearchTracksParam,
    XimalayaTrackPlayInfoParam,
)
from backend.app.iot.service.cloud.ximalaya.service import ximalaya_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base

router = APIRouter()


@router.get('/endpoints', summary='获取喜马拉雅接口清单')
async def list_ximalaya_endpoints(
    group: Annotated[str | None, Query(description='按分组过滤，例如 oauth/search/on_demand')] = None
) -> ResponseSchemaModel[list[dict[str, str]]]:
    data = ximalaya_service.list_endpoints(group=group)
    return response_base.success(data=data)


@router.post('/invoke', summary='调用注册的喜马拉雅接口')
async def invoke_ximalaya_endpoint(
    obj: XimalayaEndpointInvokeParam,
) -> ResponseModel:
    data = await ximalaya_service.invoke_endpoint(obj)
    return response_base.success(data=data)


@router.post('/raw', summary='按路径直接调用喜马拉雅接口')
async def invoke_ximalaya_path(
    obj: XimalayaPathInvokeParam,
) -> ResponseModel:
    data = await ximalaya_service.invoke_path(obj)
    return response_base.success(data=data)


@router.post('/categories', summary='获取喜马拉雅分类列表')
async def list_ximalaya_categories(
    obj: XimalayaListCategoriesParam,
) -> ResponseModel:
    data = await ximalaya_service.list_categories(obj)
    return response_base.success(data=data)


@router.post('/tags', summary='获取喜马拉雅标签列表')
async def list_ximalaya_tags(
    obj: XimalayaListTagsParam,
) -> ResponseModel:
    data = await ximalaya_service.list_tags(obj)
    return response_base.success(data=data)


@router.post('/albums', summary='获取喜马拉雅专辑列表')
async def list_ximalaya_albums(
    obj: XimalayaListAlbumsParam,
) -> ResponseModel:
    data = await ximalaya_service.list_albums(obj)
    return response_base.success(data=data)


@router.post('/albums/browse', summary='浏览喜马拉雅专辑内容')
async def browse_ximalaya_album(
    obj: XimalayaBrowseAlbumParam,
) -> ResponseModel:
    data = await ximalaya_service.browse_album(obj)
    return response_base.success(data=data)


@router.post('/search/albums', summary='搜索喜马拉雅专辑')
async def search_ximalaya_albums(
    obj: XimalayaSearchAlbumsParam,
) -> ResponseModel:
    data = await ximalaya_service.search_albums(obj)
    return response_base.success(data=data)


@router.post('/search/tracks', summary='搜索喜马拉雅声音')
async def search_ximalaya_tracks(
    obj: XimalayaSearchTracksParam,
) -> ResponseModel:
    data = await ximalaya_service.search_tracks(obj)
    return response_base.success(data=data)


@router.post('/tracks/play-info', summary='批量获取喜马拉雅声音播放地址')
async def batch_get_ximalaya_track_play_info(
    obj: XimalayaTrackPlayInfoParam,
) -> ResponseModel:
    data = await ximalaya_service.batch_get_track_play_info(obj)
    return response_base.success(data=data)
