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
    async def _get_ref(*, db: AsyncSession, ref_type: ProductRefType, ref_id: int):
        if ref_type == 'toy':
            ref = await toy_dao.get(db, ref_id)
            if ref is None:
                raise errors.NotFoundError(msg='关联的玩偶不存在')
            return ref

        if ref_type == 'toy_series':
            ref = await toy_series_dao.get(db, ref_id)
            if ref is None:
                raise errors.NotFoundError(msg='关联的玩偶系列不存在')
            return ref

        raise errors.RequestError(msg='不支持的商品关联类型')

    @classmethod
    async def _validate_relation(
            cls,
            *,
            db: AsyncSession,
            ref_type: ProductRefType,
            ref_id: int,
            parent_id: int | None,
            product_id: int | None = None,
    ) -> None:
        ref = await cls._get_ref(db=db, ref_type=ref_type, ref_id=ref_id)

        if ref_type == 'toy_series':
            if parent_id is not None:
                raise errors.RequestError(msg='系列玩偶商品不能设置父商品')
            return

        if parent_id is None:
            return
        if product_id is not None and parent_id == product_id:
            raise errors.RequestError(msg='商品不能将自身设置为父商品')

        parent = await product_dao.get(db, parent_id)
        if parent is None:
            raise errors.NotFoundError(msg='父商品不存在')
        if parent.parent_id is not None:
            raise errors.RequestError(msg='商品只支持一层父子关系')
        if parent.ref_type != 'toy_series':
            raise errors.RequestError(msg='父商品必须是系列玩偶商品')
        if ref.series_id != parent.ref_id:
            raise errors.RequestError(msg='玩偶不属于父商品关联的玩偶系列')

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
            parent_id: int | None = None,
            ref_type: ProductRefType | None = None,
            ref_id: int | None = None,
            name: str | None = None,
            status: int | None = None,
    ) -> dict[str, Any]:
        stmt = await product_dao.get_select(
            parent_id=parent_id,
            ref_type=ref_type,
            ref_id=ref_id,
            name=ProductService._normalize_text(name),
            status=status,
        )
        return await paging_data(db, stmt)

    @staticmethod
    async def create_product(*, db: AsyncSession, obj: CreateProductParam):
        await ProductService._validate_relation(
            db=db,
            ref_type=obj.ref_type,
            ref_id=obj.ref_id,
            parent_id=obj.parent_id,
        )
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
        parent_id = payload.get('parent_id', product.parent_id)
        if ref_type is None:
            raise errors.RequestError(msg='商品必须指定关联对象类型')
        if ref_id is None:
            raise errors.RequestError(msg='商品必须关联业务对象')

        has_children = await product_dao.has_children(db, parent_id=pk)
        if has_children and (
                ref_type != product.ref_type
                or ref_id != product.ref_id
                or parent_id is not None
        ):
            raise errors.ConflictError(msg='商品包含子商品，不能修改关联对象或设置父商品')

        await ProductService._validate_relation(
            db=db,
            ref_type=ref_type,
            ref_id=ref_id,
            parent_id=parent_id,
            product_id=pk,
        )

        try:
            return await product_dao.update(db, pk, payload)
        except IntegrityError:
            raise errors.ServerError(msg='更新商品失败，请稍后重试') from None

    @staticmethod
    async def delete_product(*, db: AsyncSession, pk: int) -> int:
        await ProductService.get_product(db=db, pk=pk)
        if await product_dao.has_children(db, parent_id=pk):
            raise errors.ConflictError(msg='商品包含子商品，不能删除')
        return await product_dao.delete(db, pk)


product_service = ProductService()
