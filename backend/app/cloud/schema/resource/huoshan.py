# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : huoshan.py
@Author  : OpenAI
@Date    : 2026/04/13
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from backend.common.schema import SchemaBase

HuoshanVoiceState = Literal['Unknown', 'Training', 'Success', 'Active', 'Expired', 'Reclaimed']
HuoshanAudioFormat = Literal['mp3']


class HuoshanSchemaBase(SchemaBase):
    model_config = ConfigDict(populate_by_name=True)


def _strip_required_text(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    return value


def _strip_optional_text(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


class HuoshanVoiceListParam(HuoshanSchemaBase):
    project_name: str | None = Field('default', alias='ProjectName', description='Project name')
    speaker_ids: list[str] | None = Field(None, alias='SpeakerIDs', description='Speaker ID list')
    state: HuoshanVoiceState | None = Field('Success', alias='State', description='Voice state filter')
    page_number: int | None = Field(None, alias='PageNumber', gt=0, description='Page number')
    page_size: int | None = Field(None, alias='PageSize', ge=1, description='Page size')

    @property
    def speaker_id(self) -> str | None:
        if not self.speaker_ids or len(self.speaker_ids) != 1:
            return None
        return str(self.speaker_ids[0]).strip() or None


class HuoshanToyStoryScriptParam(HuoshanSchemaBase):
    toy_ids: list[int] = Field(min_length=1, max_length=10, description='Toy ID list')
    text: str = Field(min_length=1, max_length=2000, description='Story requirement from the user')
    c_toy_id: int | None = Field(None, gt=0, description='C-position toy ID, null means no designated center toy')

    @field_validator('toy_ids')
    @classmethod
    def deduplicate_toy_ids(cls, value: list[int]) -> list[int]:
        return list(dict.fromkeys(value))

    @field_validator('text', mode='before')
    @classmethod
    def strip_text(cls, value: Any) -> Any:
        return _strip_required_text(value)

    @model_validator(mode='after')
    def validate_c_toy_id(self) -> 'HuoshanToyStoryScriptParam':
        if self.c_toy_id is not None and self.c_toy_id not in self.toy_ids:
            raise ValueError('c_toy_id must be included in toy_ids')
        return self


class HuoshanStorySynthesisParam(HuoshanSchemaBase):
    story_content: str = Field(description='Story content')
    speaker: str = Field(description='Speaker ID, supports cloned or public voices')
    speech_rate: int = Field(0, description='Speech rate')
    loudness_rate: int = Field(0, description='Voice loudness rate')
    bgm_song_id: int | None = Field(None, gt=0, description='Background music song ID')
    bgm_volume: int = Field(50, ge=0, le=100, description='Background music volume')


class HuoshanStoryGenerateParam(HuoshanSchemaBase):
    topic: str = Field(min_length=1, max_length=200, description='Story topic')


class HuoshanStreamTTSParam(HuoshanSchemaBase):
    text: str = Field(min_length=1, max_length=5000, description='TTS text content')
    speaker: str = Field(min_length=1, description='Speaker ID')
    speech_rate: int = Field(0, description='Speech rate')
    loudness_rate: int = Field(0, description='Voice loudness rate')


class HuoshanStreamTTSResult(HuoshanSchemaBase):
    request_id: str = Field(description='TTS request ID')


class HuoshanToyStoryScriptLine(HuoshanSchemaBase):
    toy_id: int = Field(gt=0, description='Toy ID')
    text: str = Field(min_length=1, description='Story line content')
    tts_token: str | None = Field(None, description='TTS token for direct playback')
    tts_status: bool = Field(False, description='Whether TTS audio has been submitted')

    @field_validator('text', mode='before')
    @classmethod
    def strip_text(cls, value: Any) -> Any:
        return _strip_required_text(value)


class HuoshanToyStoryToyInfo(HuoshanSchemaBase):
    toy_id: int = Field(gt=0, description='Toy ID')
    name: str = Field(description='Toy name')
    summary: str = Field('', description='Toy summary')
    system_prompt: str = Field('', description='Toy system prompt')
    speaker: str = Field('', description='TTS speaker ID')
    voice_name: str = Field('', description='TTS voice name')
    speech_rate: int | None = Field(0, description='Speech rate')
    loudness_rate: int | None = Field(0, description='Voice loudness rate')


class HuoshanToyStoryScriptResult(HuoshanSchemaBase):
    task_id: str = Field(description='Story script generation task ID')
    toy_ids: list[int] = Field(description='Requested toy IDs')
    text: str = Field(description='Story requirement from the user')
    c_toy_id: int | None = Field(None, gt=0, description='Designated C-position toy ID')
    model: str = Field(description='Model name')
    toys: list[HuoshanToyStoryToyInfo] = Field(default_factory=list, description='Cached toy snapshot')
    lines: list[HuoshanToyStoryScriptLine] = Field(default_factory=list, description='Generated script lines')
    device_id: int = Field(ge=1, description='Task owner device ID')
    is_completed: bool = Field(description='Whether story script generation is completed')
    task_status: int = Field(description='Task status')
    error_message: str | None = Field(None, description='Task error message')


class HuoshanStoryGenerateResult(HuoshanSchemaBase):
    task_id: str = Field(description='Story generation task ID')
    topic: str = Field(description='Story topic')
    model: str = Field(description='Model name')
    story_content: str | None = Field(None, description='Generated story content')
    is_completed: bool = Field(description='Whether story generation is completed')
    task_status: int = Field(description='Task status')
    error_message: str | None = Field(None, description='Task error message')


class HuoshanVoiceModelTypeDetail(HuoshanSchemaBase):
    model_type: int | None = Field(None, alias='ModelType', description='Model type')
    demo_audio: str | None = Field(None, alias='DemoAudio', description='Demo audio URL')
    icl_speaker_id: str | None = Field(None, alias='IclSpeakerId', description='ICL speaker ID')
    resource_id: str | None = Field(None, alias='ResourceID', description='Resource ID')


class HuoshanVoiceStatus(HuoshanSchemaBase):
    create_time: int | None = Field(None, alias='CreateTime', description='Create time')
    demo_audio: str | None = Field(None, alias='DemoAudio', description='Demo audio URL')
    instance_no: str | None = Field(None, alias='InstanceNO', description='Instance number')
    is_activable: bool | None = Field(None, alias='IsActivable', description='Whether it can be activated')
    speaker_id: str | None = Field(None, alias='SpeakerID', description='Speaker ID')
    resource_id: str | None = Field(None, description='Resolved TTS resource ID')
    state: HuoshanVoiceState | None = Field(None, alias='State', description='Voice state')
    version: str | None = Field(None, alias='Version', description='Training version')
    expire_time: int | None = Field(None, alias='ExpireTime', description='Expire time')
    order_time: int | None = Field(None, alias='OrderTime', description='Order time')
    speaker_alias: str | None = Field(None, alias='Alias', description='Speaker alias')
    available_training_times: int | None = Field(None, alias='AvailableTrainingTimes',
                                                 description='Remaining trainings')
    model_type_details: list[HuoshanVoiceModelTypeDetail] = Field(
        default_factory=list,
        alias='ModelTypeDetails',
        description='Model type detail list',
    )


class HuoshanVoiceListResult(HuoshanSchemaBase):
    app_id: int | str | None = Field(None, alias='AppID', description='App ID')
    total_count: int | None = Field(None, alias='TotalCount', description='Total count')
    next_token: str | None = Field(None, alias='NextToken', description='Next token')
    page_number: int | None = Field(None, alias='PageNumber', description='Page number')
    page_size: int | None = Field(None, alias='PageSize', description='Page size')
    statuses: list[HuoshanVoiceStatus] = Field(default_factory=list, alias='Statuses', description='Voice status list')


class HuoshanStoryBgmInfo(HuoshanSchemaBase):
    song_id: int = Field(description='Background music ID')
    title: str = Field(description='Background music title')
    play_url: str = Field(description='Background music play URL')
    artist: str | None = Field(None, description='Artist')
    duration: int = Field(description='Duration in seconds')


class HuoshanPublicVoiceInfo(HuoshanSchemaBase):
    speaker: str = Field(description='Public speaker ID')
    name: str = Field(description='Public speaker name')
    resource_id: str = Field(description='TTS resource ID')


class HuoshanStorySynthesisResult(HuoshanSchemaBase):
    task_id: str = Field(description='Huoshan task ID')
    submit_request_id: str | None = Field(None, description='Submit request ID')
    speaker: str = Field(description='Speaker ID')
    speaker_alias: str | None = Field(None, description='Speaker alias')
    speaker_state: HuoshanVoiceState | None = Field(None, description='Speaker state')
    resource_id: str = Field(description='Resource ID')
    audio_format: HuoshanAudioFormat = Field(description='Audio format')
    bgm: HuoshanStoryBgmInfo | None = Field(None, description='Background music info')
    bgm_volume: int = Field(description='Background music volume percent')
    speech_rate: int = Field(0, description='Speech rate')
    loudness_rate: int = Field(0, description='Voice loudness rate')
    is_completed: bool = Field(description='Whether mixed audio is ready')
    task_status: int = Field(description='Task status')
    oss_key: str | None = Field(None, description='OSS object key')
    download_url: str | None = Field(None, description='Mixed audio download URL')
    source_audio_url: str | None = Field(None, description='Original Huoshan audio URL')
    sentences: list[dict[str, Any]] = Field(default_factory=list, description='Sentence timestamp info')
    error_message: str | None = Field(None, description='Task error message')
