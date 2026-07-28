from backend.app.cloud.schema.resource.huoshan import (
    HuoshanToyStoryScriptParam,
)


def test_huoshan_toy_story_script_param_accepts_optional_save_param() -> None:
    obj = HuoshanToyStoryScriptParam.model_validate({
        'toy_ids': [1, 2],
        'text': '生成一个晚安故事',
    })

    assert obj.toy_ids == [1, 2]
    assert obj.text == '生成一个晚安故事'


def test_huoshan_toy_story_script_param_allows_submit_without_save_param() -> None:
    obj = HuoshanToyStoryScriptParam.model_validate({
        'toy_ids': [1],
        'text': '生成一个冒险故事',
    })

    assert obj.toy_ids == [1]
    assert obj.text == '生成一个冒险故事'
