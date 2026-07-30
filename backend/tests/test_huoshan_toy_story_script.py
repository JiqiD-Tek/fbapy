import pytest
from pydantic import ValidationError

from backend.app.cloud.schema.resource.huoshan import (
    HuoshanToyStoryScriptParam,
)


def test_huoshan_toy_story_script_param_accepts_optional_c_toy_id() -> None:
    obj = HuoshanToyStoryScriptParam.model_validate({
        'toy_ids': [1, 2],
        'text': '生成一个晚安故事',
        'c_toy_id': 2,
    })

    assert obj.toy_ids == [1, 2]
    assert obj.text == '生成一个晚安故事'
    assert obj.c_toy_id == 2


def test_huoshan_toy_story_script_param_allows_submit_without_c_toy_id() -> None:
    obj = HuoshanToyStoryScriptParam.model_validate({
        'toy_ids': [1],
        'text': '生成一个冒险故事',
    })

    assert obj.toy_ids == [1]
    assert obj.text == '生成一个冒险故事'
    assert obj.c_toy_id is None


def test_huoshan_toy_story_script_param_rejects_c_toy_id_not_in_toy_ids() -> None:
    with pytest.raises(ValidationError):
        HuoshanToyStoryScriptParam.model_validate({
            'toy_ids': [1, 2],
            'text': '生成一个冒险故事',
            'c_toy_id': 3,
        })
