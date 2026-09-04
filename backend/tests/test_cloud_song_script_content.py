import pytest

from pydantic import ValidationError
from sqlalchemy import JSON

from backend.app.cloud.model.resource.song import CloudSong
from backend.app.cloud.schema.resource.song import CreateSongParam, GetSongDetail, UpdateSongParam
from backend.common.pagination import PageData
from backend.common.response.response_schema import ResponseSchemaModel


def _build_script_content() -> list[dict]:
    return [
        {
            'groups': [
                {
                    'speaker': 'voice-narrator',
                    'speech_rate': 0,
                    'loudness_rate': 10,
                    'text': '旁白开场。',
                },
                {
                    'speaker': 'voice-child',
                    'speech_rate': 5,
                    'loudness_rate': 0,
                    'text': '我们出发吧！',
                },
            ],
            'audio_url': 'https://cdn.example.com/segments/1.mp3',
        },
        {
            'groups': [
                {
                    'speaker': 'voice-narrator',
                    'speech_rate': -5,
                    'loudness_rate': 5,
                    'text': '故事还在继续。',
                }
            ],
            'audio_url': None,
        },
    ]


def test_create_song_accepts_segmented_script_content() -> None:
    obj = CreateSongParam.model_validate(
        {
            'title': '多人故事',
            'content_type': 2,
            'play_url': 'https://cdn.example.com/songs/complete.mp3',
            'script_content': _build_script_content(),
        }
    )

    assert len(obj.script_content) == 2
    assert len(obj.script_content[0].groups) == 2
    assert obj.script_content[0].groups[1].speaker == 'voice-child'
    assert obj.script_content[0].audio_url == 'https://cdn.example.com/segments/1.mp3'
    assert obj.play_url == 'https://cdn.example.com/songs/complete.mp3'


def test_song_defaults_script_content_to_empty_list() -> None:
    first = CreateSongParam.model_validate({'title': '普通歌曲', 'content_type': 1})
    second = CreateSongParam.model_validate({'title': '另一首歌曲', 'content_type': 1})

    assert first.script_content == []
    assert first.script_content is not second.script_content


def test_song_normalizes_legacy_null_script_content() -> None:
    obj = CreateSongParam.model_validate({'title': '旧歌曲', 'content_type': 1, 'script_content': None})

    assert obj.script_content == []


def test_song_detail_normalizes_legacy_null_script_content() -> None:
    song = CloudSong(title='旧歌曲', content_type=1, script_content=None)
    song.id = 1

    detail = GetSongDetail.model_validate(song)

    assert detail.script_content == []


def test_song_detail_normalizes_paginated_dict_with_null_script_content() -> None:
    detail = GetSongDetail.model_validate(
        {
            'id': 1,
            'title': '旧歌曲',
            'content_type': 1,
            'script_content': None,
            'created_time': '2026-09-04T00:00:00+08:00',
        }
    )

    assert detail.script_content == []


def test_song_page_response_normalizes_null_script_content() -> None:
    response_type = ResponseSchemaModel[PageData[GetSongDetail]]
    response = response_type.model_validate(
        {
            'code': 200,
            'msg': 'success',
            'data': {
                'items': [
                    {
                        'id': 1,
                        'title': '旧歌曲',
                        'content_type': 1,
                        'script_content': None,
                        'created_time': '2026-09-04T00:00:00+08:00',
                    }
                ],
                'total': 1,
                'page': 1,
                'size': 20,
                'total_pages': 1,
                'links': {
                    'first': '/songs?page=1&size=20',
                    'last': '/songs?page=1&size=20',
                    'self': '/songs?page=1&size=20',
                    'next': None,
                    'prev': None,
                },
            },
        }
    )

    assert response.data.items[0].script_content == []


def test_update_song_serializes_nested_script_content_for_json_column() -> None:
    obj = UpdateSongParam.model_validate({'script_content': _build_script_content()})

    assert obj.model_dump(exclude_unset=True) == {'script_content': _build_script_content()}


def test_update_song_omits_script_content_when_not_provided() -> None:
    obj = UpdateSongParam.model_validate({'title': '新标题'})

    assert obj.model_dump(exclude_unset=True) == {'title': '新标题'}


def test_update_song_rejects_null_script_content() -> None:
    with pytest.raises(ValidationError):
        UpdateSongParam.model_validate({'script_content': None})


def test_song_script_segment_requires_at_least_one_group() -> None:
    with pytest.raises(ValidationError):
        CreateSongParam.model_validate(
            {
                'title': '无效歌曲',
                'content_type': 2,
                'script_content': [{'groups': [], 'audio_url': None}],
            }
        )


def test_cloud_song_model_uses_json_script_content_column() -> None:
    column = CloudSong.__table__.columns.script_content
    first = CloudSong(title='第一首歌曲', content_type=1)
    second = CloudSong(title='第二首歌曲', content_type=1)

    assert isinstance(column.type, JSON)
    assert column.nullable is True
    assert column.comment == '多片段音频合成脚本'
    assert first.script_content == []
    assert first.script_content is not second.script_content
