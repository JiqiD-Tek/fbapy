# -*- coding: UTF-8 -*-
"""商城商品管理接口。"""

from typing import Annotated

from fastapi import APIRouter, Path, Query

from backend.app.cloud.schema.device.product import (
    CreateProductParam,
    GetProductDetail,
    ProductRefType,
    UpdateProductParam,
)
from backend.app.cloud.service.product_service import product_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('', summary='分页获取商品列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_product_paginated(
        db: CurrentSession,
        parent_id: Annotated[int | None, Query(description='父商品 ID', gt=0)] = None,
        ref_type: Annotated[ProductRefType | None, Query(description='关联对象类型：toy_series、toy')] = None,
        ref_id: Annotated[int | None, Query(description='关联对象 ID', gt=0)] = None,
        name: Annotated[str | None, Query(description='商品名称')] = None,
        status: Annotated[int | None, Query(description='状态：0 草稿，1 上架，2 下架')] = None,
) -> ResponseSchemaModel[PageData[GetProductDetail]]:
    page_data = await product_service.get_product_list(
        db=db,
        parent_id=parent_id,
        ref_type=ref_type,
        ref_id=ref_id,
        name=name,
        status=status,
    )
    page_data['items'] = [GetProductDetail.model_validate(item) for item in page_data['items']]
    return response_base.success(data=page_data)


@router.post('', summary='创建商品', dependencies=[DependsJwtAuth])
async def create_product(
        db: CurrentSessionTransaction,
        obj: CreateProductParam,
) -> ResponseSchemaModel[GetProductDetail]:
    product = await product_service.create_product(db=db, obj=obj)
    return response_base.success(data=GetProductDetail.model_validate(product))


@router.get('/{pk}', summary='获取商品详情', dependencies=[DependsJwtAuth])
async def get_product(
        db: CurrentSession,
        pk: Annotated[int, Path(description='商品 ID')],
) -> ResponseSchemaModel[GetProductDetail]:
    product = await product_service.get_product(db=db, pk=pk)
    return response_base.success(data=GetProductDetail.model_validate(product))


@router.put('/{pk}', summary='更新商品', dependencies=[DependsJwtAuth])
async def update_product(
        db: CurrentSessionTransaction,
        pk: Annotated[int, Path(description='商品 ID')],
        obj: UpdateProductParam,
) -> ResponseModel:
    count = await product_service.update_product(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/{pk}', summary='删除商品', dependencies=[DependsJwtAuth])
async def delete_product(
        db: CurrentSessionTransaction,
        pk: Annotated[int, Path(description='商品 ID')],
) -> ResponseModel:
    count = await product_service.delete_product(db=db, pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()
