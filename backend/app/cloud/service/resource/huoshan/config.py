# -*- coding: UTF-8 -*-
"""
Huoshan voice catalog.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.core.conf import settings

DEFAULT_PROJECT_NAME = 'default'


@dataclass(frozen=True, slots=True)
class VoiceProfile:
    id: str
    name: str
    desc: str = ''
    tag: tuple[str, ...] = field(default_factory=tuple)


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


VOICE_PROJECTS: tuple[VoiceProject, ...] = (
    _build_project(
        name=DEFAULT_PROJECT_NAME,
        app_id=settings.BYTES_TTS_APPID,
        access_token=settings.BYTES_TTS_TOKEN,
        voices=(
            VoiceProfile(
                id='S_GKcK2x2X1',
                name='曲老师',
                desc='曲老师像一位耐心又有经验的启蒙老师，语气清晰、节奏稳当，讲故事时有亲和力，读知识内容时也很自然。整体声线温暖克制，不会过分夸张，适合需要陪伴感和引导感的内容场景。',
                tag=('亲切自然', '表达清晰', '陪伴感强'),
            ),
            VoiceProfile(
                id='S_EKcK2x2X1',
                name='虾球',
                desc='虾球是调皮又机灵的小队长，外形是一只红色龙虾，头顶有一对会发光的大钳子。它做事很快，脑袋里总有很多鬼点子，常常还没想完就先冲出去。遇到关键问题时，它又会很快冷静下来，愿意认错，也愿意保护朋友。',
                tag=('调皮机灵', '行动很快', '关键时刻会担当'),
            ),
            VoiceProfile(
                id='S_DKcK2x2X1',
                name='米粒',
                desc='米粒的声音轻巧灵动，像一个敏感又充满好奇心的小伙伴。说话时带着一点俏皮和明亮感，能把日常内容讲得更有画面，也很适合偏童趣、偏生活化的互动表达。',
                tag=('轻巧灵动', '童趣自然', '亲近活泼'),
            ),
            VoiceProfile(
                id='S_CKcK2x2X1',
                name='旁白',
                desc='旁白音色整体中性、稳定、克制，适合承担叙述和串联内容的角色。它不会抢戏，但能把节奏托住，让故事结构更清楚，也适合说明性较强的文本内容。',
                tag=('中性稳重', '节奏平稳', '叙述感强'),
            ),
            VoiceProfile(
                id='S_BKcK2x2X1',
                name='珍棒',
                desc='珍棒的声音带着一点外放的热情和精神劲，听起来利落、有朝气，适合更活跃、更有互动感的表达方式。用在鼓励、互动问答和节奏偏快的内容里，会显得很有带动感。',
                tag=('有活力', '节奏明快', '互动感强'),
            ),
            VoiceProfile(
                id='S_AKcK2x2X1',
                name='珍居',
                desc='珍居的声音偏温和安定，像熟悉的家人陪在身边轻声说话。它不张扬，但有稳定的陪伴感，适合睡前、安抚、日常陪伴类的内容，也适合情绪比较柔和的故事场景。',
                tag=('温和安定', '居家陪伴', '适合睡前'),
            ),
            VoiceProfile(
                id='S_zKcK2x2X1',
                name='凯叔',
                desc='凯叔的声音成熟、沉稳，又带一点讲述者的画面感，适合有起承转合的故事表达。整体气质可靠、有代入感，讲冒险、成长、探索类内容时会显得更有吸引力。',
                tag=('成熟稳重', '故事感强', '代入感好'),
            ),
            VoiceProfile(
                id='S_yKcK2x2X1',
                name='成男温柔',
                desc='成男温柔是一种低刺激、温和稳定的成年男性声线，听感舒展，不压迫，也不冷淡。适合做陪伴式对话、耐心解释和情绪承接，让内容更有安全感。',
                tag=('温柔低沉', '稳定耐听', '安全感强'),
            ),
            VoiceProfile(
                id='S_xKcK2x2X1',
                name='成女温柔',
                desc='成女温柔的声音柔和细腻，表达自然，能把内容说得更贴近人。它适合用于安抚、陪伴、轻声引导和日常交流类场景，整体听感舒适，容易让人放松下来。',
                tag=('柔和细腻', '轻声陪伴', '舒适耐听'),
            ),
            VoiceProfile(
                id='S_FKcK2x2X1',
                name='成女活泼',
                desc='成女活泼的声音明亮、轻快，情绪外放但不过分尖锐，适合更有互动感和感染力的内容。无论是讲轻松故事、做趣味问答，还是引导参与，都更容易带起气氛。',
                tag=('明亮轻快', '感染力强', '氛围活跃'),
            ),
        ),
    ),
    _build_project(
        name='JS61',
        app_id=settings.JS61_BYTES_TTS_APPID,
        access_token=settings.JS61_BYTES_TTS_TOKEN,
        voices=(
            VoiceProfile(
                id='S_7V2ryDOZ1',
                name='汤普森爸爸',
                desc='汤普森爸爸像一位可靠又愿意耐心交流的父亲，声线厚实、温暖，既有亲近感，也有一点沉稳的支撑力。适合成长陪伴、睡前讲述和需要建立信任感的互动内容。',
                tag=('爸爸陪伴感', '厚实温暖', '可靠沉稳'),
            ),
            VoiceProfile(
                id='S_RCrqyDOZ1',
                name='方厚鑫',
                desc='方厚鑫的声线自然稳当，听感亲近，不会过分夸张，也带一点成熟和可靠的支撑感。适合日常对话、故事讲述、轻声引导和需要稳定节奏的互动内容，整体耐听，陪伴感也比较舒服。',
                tag=('自然稳当', '亲近耐听', '引导感好'),
            ),
        ),
    ),
)

_VOICE_PROJECTS_BY_NAME = {project.name: project for project in VOICE_PROJECTS}


def list_voice_projects() -> tuple[VoiceProject, ...]:
    return VOICE_PROJECTS


def get_voice_project(project_name: str | None = None) -> VoiceProject:
    normalized_name = _normalize_text(project_name)
    return _VOICE_PROJECTS_BY_NAME.get(normalized_name) or _VOICE_PROJECTS_BY_NAME[DEFAULT_PROJECT_NAME]


def get_voice_project_for_speaker(speaker: str | None = None) -> VoiceProject:
    speaker_id = _normalize_text(speaker)
    if not speaker_id:
        return get_voice_project(DEFAULT_PROJECT_NAME)

    for project in VOICE_PROJECTS:
        if project.find_voice(speaker_id) is not None:
            return project
    return get_voice_project(DEFAULT_PROJECT_NAME)


def list_project_voices(project_name: str | None = None) -> tuple[VoiceProfile, ...]:
    return get_voice_project(project_name).voices


def find_voice_profile(
        speaker: str | None,
        *,
        project_name: str | None = None,
) -> VoiceProfile | None:
    speaker_id = _normalize_text(speaker)
    if not speaker_id:
        return None

    if project_name is not None:
        return get_voice_project(project_name).find_voice(speaker_id)

    for project in VOICE_PROJECTS:
        voice = project.find_voice(speaker_id)
        if voice is not None:
            return voice
    return None


def get_voice_name(speaker: str | None = None) -> str | None:
    voice = find_voice_profile(speaker)
    if voice is None:
        return None
    return voice.name or None
