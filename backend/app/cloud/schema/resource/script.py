# -*- coding: UTF-8 -*-
"""
Cloud script schemas.
"""

from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field, field_validator, model_validator

from backend.common.schema import SchemaBase


def _normalize_role_ids(value: list[int] | None) -> list[int] | None:
    if value is None:
        return None
    return sorted(dict.fromkeys(int(role_id) for role_id in value))


def _strip_required_text(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    return value


def _strip_optional_text(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _validate_script_role_ids(*, role_ids: list[int], content: list['ScriptLine']) -> None:
    role_id_set = set(role_ids)
    content_role_ids = {line.role_id for line in content}

    invalid_role_ids = sorted(content_role_ids - role_id_set)
    if invalid_role_ids:
        raise ValueError(f'content contains role_ids not present in role_ids: {", ".join(str(role_id) for role_id in invalid_role_ids)}')

    missing_role_ids = sorted(role_id_set - content_role_ids)
    if missing_role_ids:
        raise ValueError(f'role_ids missing from content: {", ".join(str(role_id) for role_id in missing_role_ids)}')


class ScriptLine(SchemaBase):
    role_id: int = Field(gt=0, description='Role ID')
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
    version: int = Field(default=1, ge=1, description='Version')
    summary: str | None = Field(None, description='Summary')
    cover_url: str | None = Field(None, description='Cover URL')
    author: str | None = Field(None, description='Author')
    role_ids: list[int] = Field(min_length=1, description='Role ID list')
    content: list[ScriptLine] = Field(min_length=1, description='Script line content')
    status: int = Field(default=0, description='Status (0 draft, 1 enabled, 2 disabled)')
    remark: str | None = Field(None, description='Remark')

    @field_validator('role_ids')
    @classmethod
    def normalize_role_ids(cls, value: list[int]) -> list[int]:
        return _normalize_role_ids(value) or []

    @model_validator(mode='after')
    def validate_role_ids_content(self) -> 'ScriptSchemaBase':
        _validate_script_role_ids(role_ids=self.role_ids, content=self.content)
        return self


class CreateScriptParam(ScriptSchemaBase):
    pass


class UpdateScriptParam(SchemaBase):
    title: str | None = Field(None, description='Title')
    version: int | None = Field(None, ge=1, description='Version')
    summary: str | None = Field(None, description='Summary')
    cover_url: str | None = Field(None, description='Cover URL')
    author: str | None = Field(None, description='Author')
    role_ids: list[int] | None = Field(None, min_length=1, description='Role ID list')
    content: list[ScriptLine] | None = Field(None, min_length=1, description='Script line content')
    status: int | None = Field(None, description='Status (0 draft, 1 enabled, 2 disabled)')
    remark: str | None = Field(None, description='Remark')

    @field_validator('role_ids')
    @classmethod
    def normalize_role_ids(cls, value: list[int] | None) -> list[int] | None:
        return _normalize_role_ids(value)

    @model_validator(mode='after')
    def validate_role_ids_content(self) -> 'UpdateScriptParam':
        if self.role_ids is not None and self.content is not None:
            _validate_script_role_ids(role_ids=self.role_ids, content=self.content)
        return self


class GetScriptDetail(ScriptSchemaBase):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int = Field(description='Primary key ID')
    created_time: datetime = Field(description='Created time')
    updated_time: datetime | None = Field(None, description='Updated time')
