# -*- coding: UTF-8 -*-
"""
Huoshan voice catalog.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from backend.core.conf import settings

DEFAULT_PROJECT_NAME = 'default'
CLONE_VOICE_RESOURCE_ID_V2 = 'seed-icl-2.0'
PUBLIC_VOICE_RESOURCE_ID_V1 = 'seed-tts-1.0'
PUBLIC_VOICE_RESOURCE_ID_V2 = 'seed-tts-2.0'
PUBLIC_VOICE_PROJECT_NAME = DEFAULT_PROJECT_NAME
VoiceSource = Literal['clone', 'public']


@dataclass(frozen=True, slots=True)
class VoiceProfile:
    id: str
    name: str
    source: VoiceSource = 'clone'
    resource_id: str | None = None


@dataclass(frozen=True, slots=True)
class VoiceProject:
    name: str
    app_id: str
    access_token: str
    voices: tuple[VoiceProfile, ...] = field(default_factory=tuple)

    def find_voice(self, speaker: str | None) -> VoiceProfile | None:
        speaker_id = _normalize_text(speaker)
        if not speaker_id:
            return None

        for voice in self.voices:
            if voice.id == speaker_id:
                return voice
        return None


def _normalize_text(value: Any) -> str:
    return str(value or '').strip()


def _build_voice_profiles(
        raw_voices: list[dict[str, str]] | tuple[dict[str, str], ...],
        *,
        source: VoiceSource = 'clone',
        resource_id: str | None = None,
) -> tuple[VoiceProfile, ...]:
    return tuple(
        VoiceProfile(
            id=_normalize_text(item.get('id')),
            name=_normalize_text(item.get('name')),
            source=source,
            resource_id=_normalize_text(resource_id) or None,
        )
        for item in raw_voices
        if _normalize_text(item.get('id'))
    )


def _build_project(
        *,
        name: str,
        app_id: str,
        access_token: str,
        voices: tuple[VoiceProfile, ...],
) -> VoiceProject:
    return VoiceProject(
        name=name,
        app_id=_normalize_text(app_id),
        access_token=_normalize_text(access_token),
        voices=voices,
    )


PUBLIC_VOICES_V1 = _build_voice_profiles([
    {'id': 'en_male_corey_emo_v2_mars_bigtts', 'name': 'Corey'},
    {'id': 'zh_male_shaonianzixin_moon_bigtts', 'name': 'Brayan'},
    {'id': 'ICL_zh_male_youmoshushu_tob', 'name': '幽默叔叔'},
],
    source='public',
    resource_id=PUBLIC_VOICE_RESOURCE_ID_V1,
)
PUBLIC_VOICES_V2 = _build_voice_profiles([
    {'id': 'en_female_stokie_uranus_bigtts', 'name': 'Stokie'},
],
    source='public',
    resource_id=PUBLIC_VOICE_RESOURCE_ID_V2,
)

PUBLIC_VOICES: tuple[VoiceProfile, ...] = PUBLIC_VOICES_V1 + PUBLIC_VOICES_V2
PUBLIC_VOICES_BY_ID = {voice.id: voice for voice in PUBLIC_VOICES}

VOICE_PROJECTS: tuple[VoiceProject, ...] = (
    _build_project(
        name=DEFAULT_PROJECT_NAME,
        app_id=settings.BYTES_TTS_APPID,
        access_token=settings.BYTES_TTS_TOKEN,
        voices=_build_voice_profiles([
            {'id': 'S_GKcK2x2X1', 'name': '曲老师'},
            {'id': 'S_EKcK2x2X1', 'name': '虾球'},
            {'id': 'S_DKcK2x2X1', 'name': '米粒'},
            {'id': 'S_CKcK2x2X1', 'name': '旁白'},
            {'id': 'S_BKcK2x2X1', 'name': '珍棒'},
            {'id': 'S_AKcK2x2X1', 'name': '珍居'},
            {'id': 'S_zKcK2x2X1', 'name': '凯叔'},
            {'id': 'S_yKcK2x2X1', 'name': '成男温柔'},
            {'id': 'S_xKcK2x2X1', 'name': '成女温柔'},
            {'id': 'S_FKcK2x2X1', 'name': '成女活泼'},
        ]),
    ),
    _build_project(
        name='JS61',
        app_id=settings.JS61_BYTES_TTS_APPID,
        access_token=settings.JS61_BYTES_TTS_TOKEN,
        voices=_build_voice_profiles([
            {'id': 'S_7V2ryDOZ1', 'name': '汤普森爸爸'},
            {'id': 'S_RCrqyDOZ1', 'name': '方厚鑫'},
            {'id': 'S_fz5jyDOZ1', 'name': '英文男成'},
            {'id': 'S_jBziyDOZ1', 'name': '英文女成'},
            {'id': 'S_jz2iyDOZ1', 'name': '英文儿童'},
            {'id': 'S_bpthyDOZ1', 'name': '虾球朋友旁白'},
        ]),
    ),
)

_VOICE_PROJECTS_BY_NAME = {project.name: project for project in VOICE_PROJECTS}


def list_voice_projects() -> tuple[VoiceProject, ...]:
    return VOICE_PROJECTS


def get_voice_project(project_name: str | None = None) -> VoiceProject:
    normalized_name = _normalize_text(project_name)
    return _VOICE_PROJECTS_BY_NAME.get(normalized_name) or _VOICE_PROJECTS_BY_NAME[DEFAULT_PROJECT_NAME]


def get_public_voice(speaker: str | None = None) -> VoiceProfile | None:
    speaker_id = _normalize_text(speaker)
    if not speaker_id:
        return None
    return PUBLIC_VOICES_BY_ID.get(speaker_id)


def get_voice_profile(speaker: str | None = None) -> VoiceProfile | None:
    public_voice = get_public_voice(speaker)
    if public_voice is not None:
        return public_voice

    speaker_id = _normalize_text(speaker)
    if not speaker_id:
        return None

    for project in VOICE_PROJECTS:
        voice = project.find_voice(speaker_id)
        if voice is not None:
            return voice
    return None


def get_voice_project_for_speaker(speaker: str | None = None) -> VoiceProject:
    speaker_id = _normalize_text(speaker)
    if not speaker_id:
        return get_voice_project(DEFAULT_PROJECT_NAME)

    if get_public_voice(speaker_id) is not None:
        return get_voice_project(PUBLIC_VOICE_PROJECT_NAME)

    for project in VOICE_PROJECTS:
        if project.find_voice(speaker_id) is not None:
            return project
    return get_voice_project(DEFAULT_PROJECT_NAME)


def get_voice_name(speaker: str | None = None) -> str | None:
    voice = get_voice_profile(speaker)
    if voice is None:
        return None
    return voice.name or None


def list_public_voices() -> tuple[VoiceProfile, ...]:
    return PUBLIC_VOICES
