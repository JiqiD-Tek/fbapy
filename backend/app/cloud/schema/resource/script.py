# -*- coding: UTF-8 -*-
"""
Cloud script schemas.
"""

from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field, field_validator, model_validator

from backend.common.schema import SchemaBase


def _normalize_toy_ids(value: list[int] | None) -> list[int] | None:
    if value is None:
        return None
    return sorted(dict.fromkeys(int(toy_id) for toy_id in value))


def _strip_required_text(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    return value


def _strip_optional_text(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _normalize_favorite_flag(value: Any) -> Any:
    if value is None:
        return 0
    return value


def _validate_script_toy_ids(*, toy_ids: list[int], content: list['ScriptLine']) -> None:
    toy_id_set = set(toy_ids)
    content_toy_ids = {line.toy_id for line in content}

    invalid_toy_ids = sorted(content_toy_ids - toy_id_set)
    if invalid_toy_ids:
        raise ValueError(
            f'content contains toy_ids not present in toy_ids: {", ".join(str(toy_id) for toy_id in invalid_toy_ids)}')

    missing_toy_ids = sorted(toy_id_set - content_toy_ids)
    if missing_toy_ids:
        raise ValueError(f'toy_ids missing from content: {", ".join(str(toy_id) for toy_id in missing_toy_ids)}')


class ScriptLine(SchemaBase):
    toy_id: int = Field(gt=0, description='Toy ID')
    text: str = Field(min_length=1, description='Line text')
    audio_url: str | None = Field(None, description='Line audio URL')

    @field_validator('text', mode='before')
    @classmethod
    def strip_text(cls, value: Any) -> Any:
        return _strip_required_text(value)

    @field_validator('audio_url', mode='before')
    @classmethod
    def strip_audio_url(cls, value: Any) -> Any:
        return _strip_optional_text(value)


class ScriptSchemaBase(SchemaBase):
    title: str = Field(description='Title')
    toy_ids: list[int] = Field(min_length=1, description='Toy ID list')
    content: list[ScriptLine] = Field(min_length=1, description='Script line content')
    device_id: int = Field(default=0, ge=0, description='Device ID, 0 means platform')
    favorite: int = Field(default=0, ge=0, le=1, description='Favorite flag (0 no, 1 yes)')
    version: int = Field(default=1, ge=1, description='Version')
    summary: str | None = Field(None, description='Summary')
    cover_url: str | None = Field(None, description='Cover URL')
    author: str | None = Field(None, description='Author')
    status: int = Field(default=0, description='Status (0 draft, 1 enabled, 2 disabled)')
    remark: str | None = Field(None, description='Remark')

    @field_validator('toy_ids')
    @classmethod
    def normalize_toy_ids(cls, value: list[int]) -> list[int]:
        return _normalize_toy_ids(value) or []

    @field_validator('favorite', mode='before')
    @classmethod
    def normalize_favorite(cls, value: Any) -> Any:
        return _normalize_favorite_flag(value)

    @model_validator(mode='after')
    def validate_toy_ids_content(self) -> 'ScriptSchemaBase':
        _validate_script_toy_ids(toy_ids=self.toy_ids, content=self.content)
        return self


class CreateScriptParam(ScriptSchemaBase):
    pass


class UpdateScriptFavoriteParam(SchemaBase):
    device_id: int = Field(gt=0, description='Device ID')
    favorite: int = Field(ge=0, le=1, description='Favorite flag (0 no, 1 yes)')

    @field_validator('favorite', mode='before')
    @classmethod
    def normalize_favorite(cls, value: Any) -> Any:
        return _normalize_favorite_flag(value)


class UpdateScriptParam(SchemaBase):
    device_id: int | None = Field(None, ge=0, description='Device ID, 0 means platform')
    favorite: int | None = Field(None, ge=0, le=1, description='Favorite flag (0 no, 1 yes)')
    title: str | None = Field(None, description='Title')
    version: int | None = Field(None, ge=1, description='Version')
    summary: str | None = Field(None, description='Summary')
    cover_url: str | None = Field(None, description='Cover URL')
    author: str | None = Field(None, description='Author')
    toy_ids: list[int] | None = Field(None, min_length=1, description='Toy ID list')
    content: list[ScriptLine] | None = Field(None, min_length=1, description='Script line content')
    status: int | None = Field(None, description='Status (0 draft, 1 enabled, 2 disabled)')
    remark: str | None = Field(None, description='Remark')

    @field_validator('toy_ids')
    @classmethod
    def normalize_toy_ids(cls, value: list[int] | None) -> list[int] | None:
        return _normalize_toy_ids(value)

    @field_validator('favorite', mode='before')
    @classmethod
    def normalize_favorite(cls, value: Any) -> Any:
        return _normalize_favorite_flag(value)

    @model_validator(mode='after')
    def validate_toy_ids_content(self) -> 'UpdateScriptParam':
        if self.toy_ids is not None and self.content is not None:
            _validate_script_toy_ids(toy_ids=self.toy_ids, content=self.content)
        return self


class ScriptAICreateToy(SchemaBase):
    toy_id: int = Field(gt=0, description='Toy ID')
    name: str = Field(min_length=1, max_length=128, description='Toy name')
    summary: str | None = Field(None, max_length=500, description='Toy summary')
    system_prompt: str | None = Field(None, description='Toy system prompt')

    @field_validator('name', mode='before')
    @classmethod
    def strip_name(cls, value: Any) -> Any:
        return _strip_required_text(value)

    @field_validator('summary', 'system_prompt', mode='before')
    @classmethod
    def strip_optional_text(cls, value: Any) -> Any:
        return _strip_optional_text(value)


class ScriptAICreateParam(SchemaBase):
    title: str = Field(min_length=1, max_length=256, description='Script title')
    summary: str | None = Field(None, max_length=1000, description='Script summary')
    toys: list[ScriptAICreateToy] = Field(min_length=1, max_length=10, description='Toy list')

    @field_validator('title', mode='before')
    @classmethod
    def strip_title(cls, value: Any) -> Any:
        return _strip_required_text(value)

    @field_validator('summary', mode='before')
    @classmethod
    def strip_summary(cls, value: Any) -> Any:
        return _strip_optional_text(value)

    @model_validator(mode='after')
    def validate_toys(self) -> 'ScriptAICreateParam':
        toy_ids = [toy.toy_id for toy in self.toys]
        if len(set(toy_ids)) != len(toy_ids):
            raise ValueError('toys contains duplicate toy_id')
        return self


class GetScriptDetail(ScriptSchemaBase):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int = Field(description='Primary key ID')
    created_time: datetime = Field(description='Created time')
    updated_time: datetime | None = Field(None, description='Updated time')
