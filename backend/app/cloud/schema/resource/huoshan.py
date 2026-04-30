# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : huoshan.py
@Author  : OpenAI
@Date    : 2026/04/13
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import ConfigDict, Field, model_validator

from backend.common.schema import SchemaBase

HuoshanVoiceState = Literal['Unknown', 'Training', 'Success', 'Active', 'Expired', 'Reclaimed']
HuoshanAudioFormat = Literal['mp3']
HuoshanASRAudioInputFormat = Literal['pcm', 'wav']


class HuoshanSchemaBase(SchemaBase):
    model_config = ConfigDict(populate_by_name=True)


class HuoshanVoiceTagParam(HuoshanSchemaBase):
    key: str = Field(alias='Key', description='Tag key')
    value: str = Field(alias='Value', description='Tag value')


class HuoshanVoiceResourceTagParam(HuoshanSchemaBase):
    custom_tags: dict[str, str] | None = Field(None, alias='CustomTags', description='Legacy custom tag mapping')
    project_name: str | None = Field(None, alias='ProjectName', description='Legacy project name')


class HuoshanVoiceListParam(HuoshanSchemaBase):
    project_name: str | None = Field("default", alias='ProjectName', description='Project name')
    speaker_ids: list[str] | None = Field(None, alias='SpeakerIDs', description='Speaker ID list')
    state: HuoshanVoiceState | None = Field('Success', alias='State', description='Voice state filter')
    page_number: int | None = Field(None, alias='PageNumber', gt=0, description='Page number')
    page_size: int | None = Field(None, alias='PageSize', ge=1, description='Page size')

    @property
    def speaker_id(self) -> str | None:
        if not self.speaker_ids or len(self.speaker_ids) != 1:
            return None
        return str(self.speaker_ids[0]).strip() or None


class HuoshanVoiceOrderParam(HuoshanSchemaBase):
    resource_id: str = Field('volc.megatts.voiceclone', alias='ResourceID', description='Resource ID')
    code: str = Field('Model_storage', alias='Code', description='Billing code')
    times: int = Field(alias='Times', gt=0, description='Purchase duration in months')
    quantity: int = Field(alias='Quantity', gt=0, description='Voice quantity')
    project_name: str | None = Field(None, alias='ProjectName', description='Project name')
    tags: list[HuoshanVoiceTagParam] | None = Field(None, alias='Tags', description='Resource tags')
    auto_use_coupon: bool | None = Field(None, alias='AutoUseCoupon', description='Auto coupon flag')
    coupon_id: str | None = Field(None, alias='CouponID', description='Coupon ID')
    resource_tag: HuoshanVoiceResourceTagParam | None = Field(
        None,
        alias='ResourceTag',
        description='Legacy resource_tag payload',
        exclude=True,
    )

    @model_validator(mode='before')
    @classmethod
    def migrate_legacy_resource_tag(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        copied = dict(value)
        resource_tag = copied.get('ResourceTag')
        if resource_tag is None:
            resource_tag = copied.get('resource_tag')
        if not isinstance(resource_tag, dict):
            return copied

        project_name = copied.get('ProjectName', copied.get('project_name'))
        if not project_name:
            legacy_project_name = resource_tag.get('ProjectName', resource_tag.get('project_name'))
            if legacy_project_name:
                copied['ProjectName'] = legacy_project_name

        tags = copied.get('Tags', copied.get('tags'))
        if not tags:
            custom_tags = resource_tag.get('CustomTags', resource_tag.get('custom_tags'))
            if isinstance(custom_tags, dict) and custom_tags:
                copied['Tags'] = [{'Key': key, 'Value': str(val)} for key, val in custom_tags.items()]

        return copied


class HuoshanVoiceRenewParam(HuoshanSchemaBase):
    times: int = Field(alias='Times', gt=0, description='Renew duration in months')
    speaker_ids: list[str] = Field(alias='SpeakerIDs', min_length=1, description='Speaker IDs to renew')
    auto_use_coupon: bool | None = Field(None, alias='AutoUseCoupon', description='Auto coupon flag')
    coupon_id: str | None = Field(None, alias='CouponID', description='Coupon ID')


class HuoshanStorySynthesisParam(HuoshanSchemaBase):
    story_content: str = Field(description='Story content')
    speaker: str = Field(description='Voice clone speaker ID')
    speech_rate: int = Field(0, description='Speech rate')
    bgm_song_id: int = Field(gt=0, description='Background music song ID')
    bgm_volume: int = Field(50, ge=0, le=100, description='Background music volume')


class HuoshanStoryGenerateParam(HuoshanSchemaBase):
    topic: str = Field(min_length=1, max_length=200, description='Story topic')


class HuoshanStreamTTSParam(HuoshanSchemaBase):
    text: str = Field(min_length=1, max_length=5000, description='TTS text content')
    speaker: str = Field(min_length=1, description='Speaker ID')


class HuoshanStreamTTSResult(HuoshanSchemaBase):
    request_id: str = Field(description='TTS request ID')


class HuoshanStreamASRParam(HuoshanSchemaBase):
    audio_base64: str = Field(min_length=1, description='Base64 encoded PCM or WAV audio')
    audio_format: HuoshanASRAudioInputFormat = Field('pcm', description='Input audio format')


class HuoshanStreamASRResult(HuoshanSchemaBase):
    request_id: str = Field(description='ASR request ID')
    text: str = Field('', description='Recognized text')


class HuoshanStoryGenerateResult(HuoshanSchemaBase):
    task_id: str = Field(description='Story generation task ID')
    topic: str = Field(description='Story topic')
    model: str = Field(description='Model name')
    story_content: str | None = Field(None, description='Generated story content')
    is_completed: bool = Field(description='Whether story generation is completed')
    task_status: int = Field(description='Task status')
    error_message: str | None = Field(None, description='Task error message')


class HuoshanOpenAPIErrorDetail(HuoshanSchemaBase):
    code: str | None = Field(None, alias='Code', description='Error code')
    message: str | None = Field(None, alias='Message', description='Error message')


class HuoshanOpenAPIResponseMetadata(HuoshanSchemaBase):
    request_id: str | None = Field(None, alias='RequestId', description='Request ID')
    action: str | None = Field(None, alias='Action', description='Action name')
    version: str | None = Field(None, alias='Version', description='API version')
    service: str | None = Field(None, alias='Service', description='Service name')
    region: str | None = Field(None, alias='Region', description='Region')
    error: HuoshanOpenAPIErrorDetail | None = Field(None, alias='Error', description='Error detail')


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
    state: HuoshanVoiceState | None = Field(None, alias='State', description='Voice state')
    version: str | None = Field(None, alias='Version', description='Training version')
    expire_time: int | None = Field(None, alias='ExpireTime', description='Expire time')
    order_time: int | None = Field(None, alias='OrderTime', description='Order time')
    speaker_alias: str | None = Field(None, alias='Alias', description='Speaker alias')
    speaker_remark: str | None = Field(None, description='Local speaker remark')
    available_training_times: int | None = Field(
        None,
        alias='AvailableTrainingTimes',
        description='Remaining trainings',
    )
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


class HuoshanVoiceOrderResult(HuoshanSchemaBase):
    order_ids: list[str] = Field(default_factory=list, alias='OrderIDs', description='Order ID list')


class HuoshanStoryBgmInfo(HuoshanSchemaBase):
    song_id: int = Field(description='Background music ID')
    title: str = Field(description='Background music title')
    play_url: str = Field(description='Background music play URL')
    artist: str | None = Field(None, description='Artist')
    duration: int = Field(description='Duration in seconds')


class HuoshanStorySynthesisResult(HuoshanSchemaBase):
    task_id: str = Field(description='Huoshan task ID')
    speaker: str = Field(description='Speaker ID')
    speaker_alias: str | None = Field(None, description='Speaker alias')
    speaker_state: HuoshanVoiceState | None = Field(None, description='Speaker state')
    resource_id: str = Field(description='Resource ID')
    audio_format: HuoshanAudioFormat = Field(description='Audio format')
    bgm: HuoshanStoryBgmInfo = Field(description='Background music info')
    bgm_volume: int = Field(description='Background music volume percent')
    is_completed: bool = Field(description='Whether mixed audio is ready')
    task_status: int = Field(description='Task status')
    oss_key: str | None = Field(None, description='OSS object key')
    download_url: str | None = Field(None, description='Mixed audio download URL')
    source_audio_url: str | None = Field(None, description='Original Huoshan audio URL')
    sentences: list[dict[str, Any]] = Field(default_factory=list, description='Sentence timestamp info')
    error_message: str | None = Field(None, description='Task error message')


class HuoshanVoiceOrderResponse(HuoshanSchemaBase):
    response_metadata: HuoshanOpenAPIResponseMetadata = Field(alias='ResponseMetadata', description='Response metadata')
    result: HuoshanVoiceOrderResult = Field(alias='Result', description='Order result')


class HuoshanVoiceRenewResponse(HuoshanSchemaBase):
    response_metadata: HuoshanOpenAPIResponseMetadata = Field(alias='ResponseMetadata', description='Response metadata')
    result: HuoshanVoiceOrderResult = Field(alias='Result', description='Renew result')
