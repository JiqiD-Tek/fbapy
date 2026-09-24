# -*- coding: UTF-8 -*-
"""剧本资源接口。"""

from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.cloud.schema.resource.script import (
    CreateScriptParam,
    GetScriptDetail,
    UpdateScriptFavoriteParam,
    UpdateScriptParam,
)
from backend.app.cloud.schema.resource.script_album import (
    CreateScriptAlbumParam,
    GetScriptAlbumDetail,
    UpdateScriptAlbumParam,
)
from backend.app.cloud.service.resource.script_album_service import script_album_service
from backend.app.cloud.service.resource.script_service import script_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/albums/{pk}', summary='获取剧本专辑详情', dependencies=[DependsJwtAuth])
async def get_script_album(
    db: CurrentSession,
    pk: Annotated[int, Path(description='剧本专辑 ID')],
) -> ResponseSchemaModel[GetScriptAlbumDetail]:
    data = await script_album_service.get_album(db=db, pk=pk)
    return response_base.success(data=GetScriptAlbumDetail.model_validate(data))


@router.get('/albums', summary='分页获取剧本专辑列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_script_album_paginated(
    db: CurrentSession,
    title: Annotated[str | None, Query(description='专辑标题')] = None,
    author: Annotated[str | None, Query(description='作者')] = None,
    status: Annotated[int | None, Query(description='状态：0 禁用，1 启用')] = None,
) -> ResponseSchemaModel[PageData[GetScriptAlbumDetail]]:
    page_data = await script_album_service.get_album_list(
        db=db,
        title=title,
        author=author,
        status=status,
    )
    page_data['items'] = [GetScriptAlbumDetail.model_validate(item) for item in page_data['items']]
    return response_base.success(data=page_data)


@router.post('/albums', summary='创建剧本专辑', dependencies=[DependsJwtAuth])
async def create_script_album(
    db: CurrentSessionTransaction,
    obj: CreateScriptAlbumParam,
) -> ResponseSchemaModel[GetScriptAlbumDetail]:
    album = await script_album_service.create_album(db=db, obj=obj)
    return response_base.success(data=GetScriptAlbumDetail.model_validate(album))


@router.put('/albums/{pk}', summary='更新剧本专辑', dependencies=[DependsJwtAuth])
async def update_script_album(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='剧本专辑 ID')],
    obj: UpdateScriptAlbumParam,
) -> ResponseModel:
    count = await script_album_service.update_album(db=db, pk=pk, obj=obj)
    return response_base.success() if count > 0 else response_base.fail()


@router.delete('/albums/{pk}', summary='删除剧本专辑', dependencies=[DependsJwtAuth])
async def delete_script_album(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='剧本专辑 ID')],
) -> ResponseModel:
    count = await script_album_service.delete_album(db=db, pk=pk)
    return response_base.success() if count > 0 else response_base.fail()


@router.get('/{pk}', summary='获取剧本详情', dependencies=[DependsJwtAuth])
async def get_script(
    db: CurrentSession,
    pk: Annotated[int, Path(description='剧本 ID')],
) -> ResponseSchemaModel[GetScriptDetail]:
    data = await script_service.get_script(db=db, pk=pk)
    return response_base.success(data=GetScriptDetail.model_validate(data))


@router.get('', summary='分页获取剧本列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_script_paginated(
    db: CurrentSession,
    title: Annotated[str | None, Query(description='剧本标题')] = None,
    author: Annotated[str | None, Query(description='作者')] = None,
    status: Annotated[int | None, Query(description='状态')] = None,
    baby_id: Annotated[int | None, Query(description='宝宝 ID')] = None,
    favorite: Annotated[int | None, Query(description='是否收藏：0 否，1 是')] = None,
    album_id: Annotated[int | None, Query(description='剧本专辑 ID')] = None,
    content_types: Annotated[
        list[int] | None,
        Query(description='包含指定内容类型：1语言 2科学 3社会 4艺术 5健康'),
    ] = None,
    toy_ids: Annotated[list[int] | None, Query(description='包含指定的全部玩偶 ID')] = None,
    exact_toy_ids: Annotated[list[int] | None, Query(description='完全匹配指定玩偶 ID 集合')] = None,
) -> ResponseSchemaModel[PageData[GetScriptDetail]]:
    page_data = await script_service.get_script_list(
        db=db,
        title=title,
        author=author,
        status=status,
        baby_id=baby_id,
        favorite=favorite,
        album_id=album_id,
        content_types=content_types,
        toy_ids=toy_ids,
        exact_toy_ids=exact_toy_ids,
    )
    page_data['items'] = [GetScriptDetail.model_validate(item) for item in page_data['items']]
    return response_base.success(data=page_data)


@router.post('', summary='创建剧本', dependencies=[DependsJwtAuth])
async def create_script(
    db: CurrentSessionTransaction,
    obj: CreateScriptParam,
) -> ResponseSchemaModel[GetScriptDetail]:
    script = await script_service.create_script(db=db, obj=obj)
    return response_base.success(data=GetScriptDetail.model_validate(script))


@router.put('/{pk}/favorite', summary='更新剧本收藏状态', dependencies=[DependsJwtAuth])
async def update_script_favorite(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='剧本 ID')],
    obj: UpdateScriptFavoriteParam,
) -> ResponseModel:
    count = await script_service.update_script_favorite(
        db=db,
        user_id=request.user.id,
        pk=pk,
        obj=obj,
    )
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.put('/{pk}', summary='更新剧本', dependencies=[DependsJwtAuth])
async def update_script(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='剧本 ID')],
    obj: UpdateScriptParam,
) -> ResponseModel:
    count = await script_service.update_script(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/{pk}', summary='删除剧本', dependencies=[DependsJwtAuth])
async def delete_script(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='剧本 ID')],
) -> ResponseModel:
    count = await script_service.delete_script(db=db, pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()
