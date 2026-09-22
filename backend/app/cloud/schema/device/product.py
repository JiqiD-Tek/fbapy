# -*- coding: UTF-8 -*-
"""商城商品请求和响应模型。"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, field_validator

from backend.common.schema import SchemaBase

ProductRefType = Literal['toy_series', 'toy']
PositiveProductRefId = Annotated[int, Field(gt=0)]


def _strip_text(value: object) -> object:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


class ProductReadSchemaBase(SchemaBase):
    """商品基础信息。"""

    ref_type: ProductRefType = Field(description='关联对象类型：toy_series、toy')
    ref_id: int = Field(gt=0, description='关联对象 ID')
    name: str = Field(description='商品名称')
    cover_url: str | None = Field(None, description='商品封面地址')
    summary: str | None = Field(None, description='商品简介')
    detail: str | None = Field(None, description='商品详情')
    price: int = Field(gt=0, description='商品价格，单位：分')
    purchase_url: str | None = Field(None, description='外部购买地址')
    status: int = Field(default=0, description='状态：0 草稿，1 上架，2 下架')
    sort: int = Field(default=0, description='排序值，越小越靠前')
    remark: str | None = Field(None, description='备注')


class CreateProductParam(ProductReadSchemaBase):
    """创建商品参数。"""

    name: str = Field(min_length=1, max_length=128, description='商品名称')
    cover_url: str | None = Field(None, max_length=512, description='商品封面地址')
    summary: str | None = Field(None, max_length=500, description='商品简介')
    purchase_url: str | None = Field(None, max_length=512, description='外部购买地址')
    remark: str | None = Field(None, max_length=500, description='备注')

    @field_validator('name', mode='before')
    @classmethod
    def strip_name(cls, value: object) -> object:
        return str(value).strip() if value is not None else value

    @field_validator('cover_url', 'summary', 'detail', 'purchase_url', 'remark', mode='before')
    @classmethod
    def strip_optional_text(cls, value: object) -> object:
        return _strip_text(value)


class UpdateProductParam(SchemaBase):
    """更新商品参数。"""

    ref_type: ProductRefType | None = Field(None, description='关联对象类型：toy_series、toy')
    ref_id: PositiveProductRefId | None = Field(None, description='关联对象 ID')
    name: str | None = Field(None, min_length=1, max_length=128, description='商品名称')
    cover_url: str | None = Field(None, max_length=512, description='商品封面地址')
    summary: str | None = Field(None, max_length=500, description='商品简介')
    detail: str | None = Field(None, description='商品详情')
    price: int | None = Field(None, gt=0, description='商品价格，单位：分')
    purchase_url: str | None = Field(None, max_length=512, description='外部购买地址')
    status: int | None = Field(None, ge=0, le=2, description='状态：0 草稿，1 上架，2 下架')
    sort: int | None = Field(None, description='排序值，越小越靠前')
    remark: str | None = Field(None, max_length=500, description='备注')

    @field_validator('name', mode='before')
    @classmethod
    def strip_name(cls, value: object) -> object:
        return str(value).strip() if value is not None else value

    @field_validator('cover_url', 'summary', 'detail', 'purchase_url', 'remark', mode='before')
    @classmethod
    def strip_optional_text(cls, value: object) -> object:
        return _strip_text(value)


class ProductInfo(ProductReadSchemaBase):
    """商品信息。"""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int = Field(description='商品 ID')


class GetProductDetail(ProductInfo):
    """商品详情。"""

    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
