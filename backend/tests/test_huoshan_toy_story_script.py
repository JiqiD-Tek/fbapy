import pytest
from pydantic import ValidationError

from backend.app.cloud.schema.resource.huoshan import (
    HuoshanToyStoryScriptParam,
    HuoshanToyStoryToyInfo,
)
from backend.app.cloud.service.resource.huoshan.service import huoshan_voice_service


def test_huoshan_toy_story_script_param_accepts_optional_c_toy_id() -> None:
    obj = HuoshanToyStoryScriptParam.model_validate({
        'toy_ids': [1, 2],
        'text': 'Create a bedtime toy story',
        'c_toy_id': 2,
    })

    assert obj.toy_ids == [1, 2]
    assert obj.text == 'Create a bedtime toy story'
    assert obj.c_toy_id == 2


def test_huoshan_toy_story_script_param_allows_submit_without_c_toy_id() -> None:
    obj = HuoshanToyStoryScriptParam.model_validate({
        'toy_ids': [1],
        'text': 'Create an adventure toy story',
    })

    assert obj.toy_ids == [1]
    assert obj.text == 'Create an adventure toy story'
    assert obj.c_toy_id is None


def test_huoshan_toy_story_script_param_rejects_c_toy_id_not_in_toy_ids() -> None:
    with pytest.raises(ValidationError):
        HuoshanToyStoryScriptParam.model_validate({
            'toy_ids': [1, 2],
            'text': 'Create an adventure toy story',
            'c_toy_id': 3,
        })


def test_toy_story_script_prompt_emphasizes_reply_flow_and_center_guidance() -> None:
    prompt = huoshan_voice_service._build_toy_story_script_prompt(
        toys=[
            HuoshanToyStoryToyInfo(
                toy_id=1,
                name='Fox',
                summary='Curious and brave',
                system_prompt='Likes to notice small clues and speak with lively energy.',
                speaker='speaker-1',
                voice_name='voice-1',
            )
        ],
        text='Create a short toy story about a missing star.',
        c_toy_id=1,
    )

    assert '"character_hint": "Likes to notice small clues and speak with lively energy."' in prompt
    assert '本次指定的 C 位玩偶是 [1]' in prompt
    assert '只参考提供的 summary 和 character_hint 创作' in prompt
    assert '大多数台词都应直接承接上一句中的对象、问题、动作、提议或情绪。' in (
        huoshan_voice_service.TOY_STORY_SCRIPT_SYSTEM_PROMPT
    )
    assert '而不是轮流各说各话。' in huoshan_voice_service.TOY_STORY_SCRIPT_SYSTEM_PROMPT
