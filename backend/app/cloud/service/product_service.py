# -*- coding: UTF-8 -*-
"""商城商品业务服务。"""

from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.cloud.crud.crud_product import product_dao
from backend.app.cloud.crud.crud_toy import toy_dao, toy_series_dao
from backend.app.cloud.schema.device.product import CreateProductParam, ProductRefType, UpdateProductParam
from backend.common.exception import errors
from backend.common.pagination import paging_data


class ProductService:
    """管理商城商品及其关联的玩偶对象。"""

    @staticmethod
    def _normalize_text(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @staticmethod
    async def _ensure_ref_exists(*, db: AsyncSession, ref_type: ProductRefType, ref_id: int) -> None:
        if ref_type == 'toy':
            ref = await toy_dao.get(db, ref_id)
            if ref is None:
                raise errors.NotFoundError(msg='关联的玩偶不存在')
            return

        if ref_type == 'toy_series':
            ref = await toy_series_dao.get(db, ref_id)
            if ref is None:
                raise errors.NotFoundError(msg='关联的玩偶系列不存在')
            return

        raise errors.RequestError(msg='不支持的商品关联类型')

    @staticmethod
    async def get_product(*, db: AsyncSession, pk: int):
        product = await product_dao.get(db, pk)
        if product is None:
            raise errors.NotFoundError(msg='商品不存在')
        return product

    @staticmethod
    async def get_product_list(
            *,
            db: AsyncSession,
            ref_type: ProductRefType | None = None,
            ref_id: int | None = None,
            name: str | None = None,
            status: int | None = None,
    ) -> dict[str, Any]:
        stmt = await product_dao.get_select(
            ref_type=ref_type,
            ref_id=ref_id,
            name=ProductService._normalize_text(name),
            status=status,
        )
        return await paging_data(db, stmt)

    @staticmethod
    async def create_product(*, db: AsyncSession, obj: CreateProductParam):
        await ProductService._ensure_ref_exists(db=db, ref_type=obj.ref_type, ref_id=obj.ref_id)
        try:
            return await product_dao.create(db, obj)
        except IntegrityError:
            raise errors.ServerError(msg='创建商品失败，请稍后重试') from None

    @staticmethod
    async def update_product(*, db: AsyncSession, pk: int, obj: UpdateProductParam) -> int:
        product = await ProductService.get_product(db=db, pk=pk)
        payload = obj.model_dump(exclude_unset=True)
        if not payload:
            raise errors.RequestError(msg='更新内容不能为空')

        ref_type = payload.get('ref_type', product.ref_type)
        ref_id = payload.get('ref_id', product.ref_id)
        if ref_id is None:
            raise errors.RequestError(msg='商品必须关联业务对象')
        await ProductService._ensure_ref_exists(db=db, ref_type=ref_type, ref_id=ref_id)

        try:
            return await product_dao.update(db, pk, payload)
        except IntegrityError:
            raise errors.ServerError(msg='更新商品失败，请稍后重试') from None

    @staticmethod
    async def delete_product(*, db: AsyncSession, pk: int) -> int:
        await ProductService.get_product(db=db, pk=pk)
        return await product_dao.delete(db, pk)


product_service = ProductService()
