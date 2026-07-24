# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : toy.py
@Author  : OpenAI
@Date    : 2026/07/06
"""

from datetime import datetime
from typing import Annotated, Any

from pydantic import ConfigDict, Field, field_validator, model_validator

from backend.common.schema import SchemaBase

PositiveToyId = Annotated[int, Field(gt=0)]


def _strip_required_text(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    return value


def _strip_optional_text(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _deduplicate_toy_ids(value: list[int] | None) -> list[int] | None:
    if value is None:
        return None
    return list(dict.fromkeys(value))


class ToySeriesReadSchemaBase(SchemaBase):
    name: str = Field(description='Toy series name')
    image_url: str | None = Field(None, description='Toy series image URL')
    purchase_url: str | None = Field(None, description='Toy series purchase URL')
    description: str | None = Field(None, description='Toy series description')
    status: int = Field(default=1, description='Status: 0 disabled, 1 enabled')
    sort: int = Field(default=0, description='Sort value, lower comes first')


class CreateToySeriesParam(SchemaBase):
    name: str = Field(min_length=1, max_length=64, description='Toy series name')
    image_url: str | None = Field(None, max_length=512, description='Toy series image URL')
    purchase_url: str | None = Field(None, max_length=512, description='Toy series purchase URL')
    description: str | None = Field(None, max_length=500, description='Toy series description')
    status: int = Field(default=1, description='Status: 0 disabled, 1 enabled')
    sort: int = Field(default=0, description='Sort value, lower comes first')

    @field_validator('name', mode='before')
    @classmethod
    def strip_name(cls, value: Any) -> Any:
        return _strip_required_text(value)

    @field_validator('image_url', 'purchase_url', 'description', mode='before')
    @classmethod
    def strip_optional_text(cls, value: Any) -> Any:
        return _strip_optional_text(value)


class UpdateToySeriesParam(SchemaBase):
    name: str | None = Field(None, min_length=1, max_length=64, description='Toy series name')
    image_url: str | None = Field(None, max_length=512, description='Toy series image URL')
    purchase_url: str | None = Field(None, max_length=512, description='Toy series purchase URL')
    description: str | None = Field(None, max_length=500, description='Toy series description')
    status: int | None = Field(None, description='Status: 0 disabled, 1 enabled')
    sort: int | None = Field(None, description='Sort value, lower comes first')

    @field_validator('name', mode='before')
    @classmethod
    def strip_name(cls, value: Any) -> Any:
        return _strip_required_text(value)

    @field_validator('image_url', 'purchase_url', 'description', mode='before')
    @classmethod
    def strip_optional_text(cls, value: Any) -> Any:
        return _strip_optional_text(value)


class ToySeriesInfo(ToySeriesReadSchemaBase):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int = Field(description='Toy series ID')


class GetToySeriesDetail(ToySeriesInfo):
    created_time: datetime = Field(description='Created time')
    updated_time: datetime | None = Field(None, description='Updated time')


class ToyReadSchemaBase(SchemaBase):
    series_id: int | None = Field(None, description='Toy series ID')
    name: str | None = Field(None, description='Toy name')
    system_prompt: str | None = Field(None, description='System prompt')
    avatar_url: str | None = Field(None, description='Toy avatar URL')
    purchase_url: str | None = Field(None, description='Toy purchase URL')
    summary: str | None = Field(None, description='Toy summary')
    related_toy_ids: list[int] | None = Field(None, description='Related toy ID list')
    nfc_code: str | None = Field(None, description='NFC code')
    voice_provider: str | None = Field(None, description='Voice provider')
    voice_id: str | None = Field(None, description='Voice ID')
    voice_type: int | None = Field(None, ge=1, description='Voice type')
    voice_name: str | None = Field(None, description='Voice name')
    voice_language: str | None = Field(None, description='Voice language, such as zh-CN or en-US')
    status: int = Field(default=1, description='Status: 0 disabled, 1 enabled')
    sort: int = Field(default=0, description='Sort value, lower comes first')
    remark: str | None = Field(None, description='Remark')


class CreateToyParam(SchemaBase):
    series_id: int | None = Field(None, gt=0, description='Toy series ID')
    name: str = Field(min_length=1, max_length=128, description='Toy name')
    system_prompt: str = Field(min_length=1, description='System prompt')
    avatar_url: str | None = Field(None, max_length=512, description='Toy avatar URL')
    purchase_url: str | None = Field(None, max_length=512, description='Toy purchase URL')
    summary: str | None = Field(None, max_length=500, description='Toy summary')
    related_toy_ids: list[PositiveToyId] | None = Field(None, description='Related toy ID list')
    nfc_code: str | None = Field(None, max_length=64, description='NFC code')
    voice_provider: str | None = Field(None, max_length=64, description='Voice provider')
    voice_id: str | None = Field(None, max_length=128, description='Voice ID')
    voice_type: int | None = Field(None, ge=1, description='Voice type')
    voice_name: str | None = Field(None, max_length=128, description='Voice name')
    voice_language: str | None = Field(None, max_length=32, description='Voice language, such as zh-CN or en-US')
    status: int = Field(default=1, description='Status: 0 disabled, 1 enabled')
    sort: int = Field(default=0, description='Sort value, lower comes first')
    remark: str | None = Field(None, max_length=500, description='Remark')

    @field_validator('name', 'system_prompt', mode='before')
    @classmethod
    def strip_required_text(cls, value: Any) -> Any:
        return _strip_required_text(value)

    @field_validator(
        'avatar_url',
        'purchase_url',
        'summary',
        'nfc_code',
        'voice_provider',
        'voice_id',
        'voice_name',
        'voice_language',
        'remark',
        mode='before',
    )
    @classmethod
    def strip_optional_text(cls, value: Any) -> Any:
        return _strip_optional_text(value)

    @field_validator('related_toy_ids')
    @classmethod
    def deduplicate_related_toy_ids(cls, value: list[int] | None) -> list[int] | None:
        return _deduplicate_toy_ids(value)

    @model_validator(mode='after')
    def validate_voice_binding(self) -> 'CreateToyParam':
        if (self.voice_provider is None) != (self.voice_id is None):
            raise ValueError('voice_provider and voice_id must both be empty or both have values')
        return self


class UpdateToyParam(SchemaBase):
    series_id: int | None = Field(None, gt=0, description='Toy series ID')
    name: str | None = Field(None, min_length=1, max_length=128, description='Toy name')
    system_prompt: str | None = Field(None, min_length=1, description='System prompt')
    avatar_url: str | None = Field(None, max_length=512, description='Toy avatar URL')
    purchase_url: str | None = Field(None, max_length=512, description='Toy purchase URL')
    summary: str | None = Field(None, max_length=500, description='Toy summary')
    related_toy_ids: list[PositiveToyId] | None = Field(None, description='Related toy ID list')
    nfc_code: str | None = Field(None, max_length=64, description='NFC code')
    voice_provider: str | None = Field(None, max_length=64, description='Voice provider')
    voice_id: str | None = Field(None, max_length=128, description='Voice ID')
    voice_type: int | None = Field(None, ge=1, description='Voice type')
    voice_name: str | None = Field(None, max_length=128, description='Voice name')
    voice_language: str | None = Field(None, max_length=32, description='Voice language, such as zh-CN or en-US')
    status: int | None = Field(None, description='Status: 0 disabled, 1 enabled')
    sort: int | None = Field(None, description='Sort value, lower comes first')
    remark: str | None = Field(None, max_length=500, description='Remark')

    @field_validator('name', 'system_prompt', mode='before')
    @classmethod
    def strip_required_text(cls, value: Any) -> Any:
        return _strip_required_text(value)

    @field_validator(
        'avatar_url',
        'purchase_url',
        'summary',
        'nfc_code',
        'voice_provider',
        'voice_id',
        'voice_name',
        'voice_language',
        'remark',
        mode='before',
    )
    @classmethod
    def strip_optional_text(cls, value: Any) -> Any:
        return _strip_optional_text(value)

    @field_validator('related_toy_ids')
    @classmethod
    def deduplicate_related_toy_ids(cls, value: list[int] | None) -> list[int] | None:
        return _deduplicate_toy_ids(value)


class GenerateToySystemPromptParam(SchemaBase):
    name: str = Field(min_length=1, max_length=128, description='Toy name')
    summary: str | None = Field(None, max_length=500, description='Toy summary')

    @field_validator('name', mode='before')
    @classmethod
    def strip_name(cls, value: Any) -> Any:
        return _strip_required_text(value)

    @field_validator('summary', mode='before')
    @classmethod
    def strip_summary(cls, value: Any) -> Any:
        return _strip_optional_text(value)


class GenerateToySystemPromptResult(SchemaBase):
    system_prompt: str = Field(description='Generated system prompt')


class GetToyDetail(ToyReadSchemaBase):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int = Field(description='Toy ID')
    created_time: datetime = Field(description='Created time')
    updated_time: datetime | None = Field(None, description='Updated time')
