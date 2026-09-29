# -*- coding: UTF-8 -*-
"""火山声音、故事和语音合成接口数据模型。"""

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
    project_name: str | None = Field('default', alias='ProjectName', description='项目名称')
    speaker_ids: list[str] | None = Field(None, alias='SpeakerIDs', description='说话人 ID 列表')
    state: HuoshanVoiceState | None = Field('Success', alias='State', description='声音状态筛选')
    page_number: int | None = Field(None, alias='PageNumber', gt=0, description='页码')
    page_size: int | None = Field(None, alias='PageSize', ge=1, description='每页数量')

    @property
    def speaker_id(self) -> str | None:
        if not self.speaker_ids or len(self.speaker_ids) != 1:
            return None
        return str(self.speaker_ids[0]).strip() or None


class HuoshanToyStoryScriptParam(HuoshanSchemaBase):
    toy_ids: list[int] = Field(min_length=1, max_length=10, description='玩偶 ID 列表')
    text: str = Field(min_length=1, max_length=2000, description='用户提出的故事要求')
    c_toy_id: int | None = Field(None, gt=0, description='中心位玩偶 ID，为空表示不指定中心位玩偶')

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
            raise ValueError('中心位玩偶 ID 必须包含在玩偶 ID 列表中')
        return self


class HuoshanStorySynthesisParam(HuoshanSchemaBase):
    story_content: str = Field(description='故事内容')
    speaker: str = Field(description='说话人 ID，支持克隆声音或公共声音')
    speech_rate: int = Field(0, description='语速')
    loudness_rate: int = Field(0, description='音量')
    bgm_song_id: int | None = Field(None, gt=0, description='背景音乐歌曲 ID')
    bgm_volume: int = Field(50, ge=0, le=100, description='背景音乐音量')


class HuoshanStoryGenerateParam(HuoshanSchemaBase):
    topic: str = Field(min_length=1, max_length=200, description='故事主题')


class HuoshanStreamTTSParam(HuoshanSchemaBase):
    text: str = Field(min_length=1, max_length=5000, description='语音合成文本内容')
    speaker: str = Field(min_length=1, description='说话人 ID')
    speech_rate: int = Field(0, description='语速')
    loudness_rate: int = Field(0, description='音量')


class HuoshanStreamTTSResult(HuoshanSchemaBase):
    request_id: str = Field(description='语音合成请求 ID')


class HuoshanToyStoryScriptLine(HuoshanSchemaBase):
    toy_id: int = Field(gt=0, description='玩偶 ID')
    text: str = Field(min_length=1, description='故事台词内容')
    tts_token: str | None = Field(None, description='用于直接播放的语音合成令牌')
    tts_status: bool = Field(False, description='是否已提交语音合成')

    @field_validator('text', mode='before')
    @classmethod
    def strip_text(cls, value: Any) -> Any:
        return _strip_required_text(value)


class HuoshanToyStoryToyInfo(HuoshanSchemaBase):
    toy_id: int = Field(gt=0, description='玩偶 ID')
    name: str = Field(description='玩偶名称')
    summary: str = Field('', description='玩偶简介')
    system_prompt: str = Field('', description='玩偶系统提示词')
    speaker: str = Field('', description='语音合成说话人 ID')
    voice_name: str = Field('', description='语音合成声音名称')
    speech_rate: int | None = Field(0, description='语速')
    loudness_rate: int | None = Field(0, description='音量')


class HuoshanToyStoryScriptResult(HuoshanSchemaBase):
    task_id: str = Field(description='故事剧本生成任务 ID')
    toy_ids: list[int] = Field(description='请求的玩偶 ID 列表')
    text: str = Field(description='用户提出的故事要求')
    c_toy_id: int | None = Field(None, gt=0, description='指定的中心位玩偶 ID')
    model: str = Field(description='模型名称')
    toys: list[HuoshanToyStoryToyInfo] = Field(default_factory=list, description='缓存的玩偶快照')
    lines: list[HuoshanToyStoryScriptLine] = Field(default_factory=list, description='生成的剧本台词列表')
    baby_id: int | None = Field(None, gt=0, description='任务归属的宝宝 ID，NULL 表示平台任务')
    is_completed: bool = Field(description='故事剧本生成是否完成')
    task_status: int = Field(description='任务状态')
    error_message: str | None = Field(None, description='任务错误信息')


class HuoshanStoryGenerateResult(HuoshanSchemaBase):
    task_id: str = Field(description='故事生成任务 ID')
    topic: str = Field(description='故事主题')
    model: str = Field(description='模型名称')
    story_content: str | None = Field(None, description='生成的故事内容')
    is_completed: bool = Field(description='故事生成是否完成')
    task_status: int = Field(description='任务状态')
    error_message: str | None = Field(None, description='任务错误信息')


class HuoshanVoiceModelTypeDetail(HuoshanSchemaBase):
    model_type: int | None = Field(None, alias='ModelType', description='模型类型')
    demo_audio: str | None = Field(None, alias='DemoAudio', description='示例音频地址')
    icl_speaker_id: str | None = Field(None, alias='IclSpeakerId', description='ICL 说话人 ID')
    resource_id: str | None = Field(None, alias='ResourceID', description='资源 ID')


class HuoshanVoiceStatus(HuoshanSchemaBase):
    create_time: int | None = Field(None, alias='CreateTime', description='创建时间')
    demo_audio: str | None = Field(None, alias='DemoAudio', description='示例音频地址')
    instance_no: str | None = Field(None, alias='InstanceNO', description='实例编号')
    is_activable: bool | None = Field(None, alias='IsActivable', description='是否可以激活')
    speaker_id: str | None = Field(None, alias='SpeakerID', description='说话人 ID')
    resource_id: str | None = Field(None, description='解析后的语音合成资源 ID')
    state: HuoshanVoiceState | None = Field(None, alias='State', description='声音状态')
    version: str | None = Field(None, alias='Version', description='训练版本')
    expire_time: int | None = Field(None, alias='ExpireTime', description='过期时间')
    order_time: int | None = Field(None, alias='OrderTime', description='订阅时间')
    speaker_alias: str | None = Field(None, alias='Alias', description='说话人别名')
    available_training_times: int | None = Field(None, alias='AvailableTrainingTimes',
                                                 description='剩余训练次数')
    model_type_details: list[HuoshanVoiceModelTypeDetail] = Field(
        default_factory=list,
        alias='ModelTypeDetails',
        description='模型类型详情列表',
    )


class HuoshanVoiceListResult(HuoshanSchemaBase):
    app_id: int | str | None = Field(None, alias='AppID', description='应用 ID')
    total_count: int | None = Field(None, alias='TotalCount', description='总数量')
    next_token: str | None = Field(None, alias='NextToken', description='下一页令牌')
    page_number: int | None = Field(None, alias='PageNumber', description='页码')
    page_size: int | None = Field(None, alias='PageSize', description='每页数量')
    statuses: list[HuoshanVoiceStatus] = Field(default_factory=list, alias='Statuses', description='声音状态列表')


class HuoshanStoryBgmInfo(HuoshanSchemaBase):
    song_id: int = Field(description='背景音乐 ID')
    title: str = Field(description='背景音乐标题')
    play_url: str = Field(description='背景音乐播放地址')
    artist: str | None = Field(None, description='作者或演唱者')
    duration: int = Field(description='时长（秒）')


class HuoshanPublicVoiceInfo(HuoshanSchemaBase):
    speaker: str = Field(description='公共说话人 ID')
    name: str = Field(description='公共说话人名称')
    resource_id: str = Field(description='语音合成资源 ID')


class HuoshanStorySynthesisResult(HuoshanSchemaBase):
    task_id: str = Field(description='火山任务 ID')
    submit_request_id: str | None = Field(None, description='提交请求 ID')
    speaker: str = Field(description='说话人 ID')
    speaker_alias: str | None = Field(None, description='说话人别名')
    speaker_state: HuoshanVoiceState | None = Field(None, description='说话人状态')
    resource_id: str = Field(description='资源 ID')
    audio_format: HuoshanAudioFormat = Field(description='音频格式')
    bgm: HuoshanStoryBgmInfo | None = Field(None, description='背景音乐信息')
    bgm_volume: int = Field(description='背景音乐音量百分比')
    speech_rate: int = Field(0, description='语速')
    loudness_rate: int = Field(0, description='音量')
    is_completed: bool = Field(description='混合音频是否准备完成')
    task_status: int = Field(description='任务状态')
    oss_key: str | None = Field(None, description='OSS 对象键')
    download_url: str | None = Field(None, description='混合音频下载地址')
    source_audio_url: str | None = Field(None, description='原始火山音频地址')
    sentences: list[dict[str, Any]] = Field(default_factory=list, description='句子时间戳信息')
    error_message: str | None = Field(None, description='任务错误信息')
