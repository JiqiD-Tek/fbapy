# -*- coding: UTF-8 -*-
"""
Cloud dialogue schemas.
"""

from datetime import datetime

from pydantic import AliasChoices, ConfigDict, Field

from backend.common.schema import SchemaBase


class DialogueUtterance(SchemaBase):
    speaker: str | None = Field(None, description='Speaker ID')
    text: str = Field(description='Utterance text')
    audio_url: str | None = Field(None, description='Audio URL')


class DialogueTurn(SchemaBase):
    sequence: int = Field(ge=1, description='Turn sequence')
    delta: int | None = Field(
        None,
        ge=0,
        validation_alias=AliasChoices('delta', 'duration'),
        description='Turn playback delta in seconds',
    )
    utterances: list[DialogueUtterance] = Field(
        default_factory=list,
        min_length=1,
        description='One or more utterances in the same turn',
    )


class DialogueContent(SchemaBase):
    speakers: list[str] = Field(
        default_factory=list,
        min_length=1,
        description='Dialogue speakers',
    )
    turns: list[DialogueTurn] = Field(
        default_factory=list,
        min_length=1,
        description='Dialogue turns',
    )


class DialogueSchemaBase(SchemaBase):
    title: str = Field(description='Title')
    version: int = Field(default=1, ge=1, description='Version')
    summary: str | None = Field(None, description='Summary')
    cover_url: str | None = Field(None, description='Cover URL')
    author: str | None = Field(None, description='Author')
    content: DialogueContent = Field(description='Structured content')
    status: int = Field(default=0, description='Status (0 draft, 1 enabled, 2 disabled)')
    remark: str | None = Field(None, description='Remark')


class CreateDialogueParam(DialogueSchemaBase):
    pass


class UpdateDialogueParam(SchemaBase):
    title: str | None = Field(None, description='Title')
    version: int | None = Field(None, ge=1, description='Version')
    summary: str | None = Field(None, description='Summary')
    cover_url: str | None = Field(None, description='Cover URL')
    author: str | None = Field(None, description='Author')
    content: DialogueContent | None = Field(None, description='Structured content')
    status: int | None = Field(None, description='Status (0 draft, 1 enabled, 2 disabled)')
    remark: str | None = Field(None, description='Remark')


class GetDialogueDetail(DialogueSchemaBase):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int = Field(description='Primary key ID')
    created_time: datetime = Field(description='Created time')
    updated_time: datetime | None = Field(None, description='Updated time')
