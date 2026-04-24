# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : ximalaya.py
@Author  : OpenAI
@Date    : 2026/03/25
"""

from fastapi import APIRouter

from backend.app.cloud.schema.resource.ximalaya import (
    XimalayaBrowseAlbumParam,
    XimalayaListAlbumsParam,
    XimalayaListTagsParam,
    XimalayaRecommendedParam,
    XimalayaSearchAlbumsParam,
)
from backend.app.cloud.service.resource.ximalaya.service import ximalaya_service
from backend.common.response.response_schema import ResponseModel, response_base
from backend.common.security.jwt import DependsJwtAuth

router = APIRouter()


@router.post(
    '/recommended',
    summary='获取喜马拉雅推荐',
    # dependencies=[DependsJwtAuth]
)
async def ximalaya_recommended(
        obj: XimalayaRecommendedParam,
) -> ResponseModel:
    data = await ximalaya_service.recommend_albums(obj)
    return response_base.success(data=data)


@router.post(
    '/tags',
    summary='获取喜马拉雅标签列表',
    # dependencies=[DependsJwtAuth]
)
async def ximalaya_tags(
        obj: XimalayaListTagsParam,
) -> ResponseModel:
    data = [await ximalaya_service.list_tags(obj)]
    return response_base.success(data=data)


@router.post(
    '/albums',
    summary='获取喜马拉雅专辑列表',
    # dependencies=[DependsJwtAuth]
)
async def ximalaya_albums(
        obj: XimalayaListAlbumsParam,
) -> ResponseModel:
    data = await ximalaya_service.list_albums(obj)
    return response_base.success(data=data)


@router.post(
    '/albums/browse',
    summary='喜马拉雅专辑内容',
    # dependencies=[DependsJwtAuth]
)
async def ximalaya_album_browse(
        obj: XimalayaBrowseAlbumParam,
) -> ResponseModel:
    data = await ximalaya_service.browse_album(obj)
    return response_base.success(data=data)


@router.post(
    '/albums/search',
    summary='搜索喜马拉雅专辑',
    # dependencies=[DependsJwtAuth]
)
async def ximalaya_albums_search(
        obj: XimalayaSearchAlbumsParam,
) -> ResponseModel:
    data = await ximalaya_service.search_albums(obj)
    return response_base.success(data=data)
