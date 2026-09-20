import pytest
import sqlalchemy as sa

from pydantic import ValidationError

from backend.app.cloud.model.resource.script import CloudScript
from backend.app.cloud.schema.resource.script import CreateScriptParam, ScriptLine, UpdateScriptParam


def _build_script_payload() -> dict:
    return {
        'title': 'Bedtime Story',
        'content_types': [3, 2, 3],
        'toy_ids': [2, 1],
        'content': [
            ScriptLine(toy_id=1, text='Hello.').model_dump(mode='python'),
            ScriptLine(toy_id=2, text='Hi there.').model_dump(mode='python'),
        ],
    }


def test_create_script_param_defaults_device_id_and_favorite() -> None:
    obj = CreateScriptParam.model_validate(_build_script_payload())

    assert obj.device_id == 0
    assert obj.favorite == 0
    assert obj.content_types == [2, 3]
    assert obj.toy_ids == [1, 2]


def test_create_script_param_accepts_play_url_and_time_ranges() -> None:
    payload = _build_script_payload()
    payload['play_url'] = 'https://cdn.example.com/story.mp3'
    payload['content'] = [
        {'toy_id': 1, 'text': 'Hello.', 'start_at': '00:00:01.000', 'end_at': '00:00:02.500'},
        {'toy_id': 2, 'text': 'Hi there.', 'start_at': None, 'end_at': None},
    ]

    obj = CreateScriptParam.model_validate(payload)

    assert obj.play_url == 'https://cdn.example.com/story.mp3'
    assert obj.content[0].start_at == '00:00:01.000'
    assert obj.content[0].end_at == '00:00:02.500'
    assert 'audio_url' not in ScriptLine.model_fields


def test_update_script_param_accepts_favorite_flag() -> None:
    obj = UpdateScriptParam.model_validate({'favorite': 1})

    assert obj.favorite == 1


def test_update_script_param_accepts_content_types_and_play_url() -> None:
    obj = UpdateScriptParam.model_validate(
        {'content_types': [5, 1, 5], 'play_url': 'https://cdn.example.com/story.mp3'}
    )

    assert obj.content_types == [1, 5]
    assert obj.play_url == 'https://cdn.example.com/story.mp3'


@pytest.mark.parametrize('content_types', [[], [0], [6], [1, 6]])
def test_script_param_rejects_invalid_content_types(content_types: list[int]) -> None:
    payload = _build_script_payload()
    payload['content_types'] = content_types

    with pytest.raises(ValidationError):
        CreateScriptParam.model_validate(payload)


def test_cloud_script_model_has_favorite_and_play_url_columns() -> None:
    favorite_column = CloudScript.__table__.columns.favorite
    content_types_column = CloudScript.__table__.columns.content_types
    play_url_column = CloudScript.__table__.columns.play_url

    assert favorite_column.default is not None
    assert favorite_column.default.arg == 0
    assert favorite_column.server_default is not None
    assert str(favorite_column.server_default.arg) == '0'
    assert favorite_column.comment == 'Favorite flag (0 no, 1 yes)'
    assert isinstance(content_types_column.type, sa.JSON)
    assert content_types_column.comment == '内容类型列表（1语言 2科学 3社会 4艺术 5健康）'
    assert play_url_column.type.length == 1000
    assert play_url_column.comment == '播放地址'
