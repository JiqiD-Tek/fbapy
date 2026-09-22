import pytest

from pydantic import ValidationError

from backend.app.cloud.model import Script, ScriptAlbum, Song, SongAlbum
from backend.app.cloud.schema.resource.script import CreateScriptParam
from backend.app.cloud.schema.resource.script_album import CreateScriptAlbumParam


def test_resource_model_names_and_tables_are_consistent() -> None:
    assert SongAlbum.__tablename__ == 'u_song_album'
    assert Song.__tablename__ == 'u_song'
    assert ScriptAlbum.__tablename__ == 'u_script_album'
    assert Script.__tablename__ == 'u_script'


def test_script_album_normalizes_toy_ids() -> None:
    album = CreateScriptAlbumParam(title='森林故事', toy_ids=[3, 1, 3, 2])

    assert album.toy_ids == [1, 2, 3]
    assert album.description is None


def test_script_album_rejects_empty_toy_ids() -> None:
    with pytest.raises(ValidationError):
        CreateScriptAlbumParam(title='森林故事', toy_ids=[])


def test_script_uses_album_and_track_fields_without_duplicate_toy_ids() -> None:
    script = CreateScriptParam(
        album_id=8,
        title='第一集',
        content=[{'toy_id': 1, 'text': '你好'}],
        duration=65,
        track_no=1,
    )

    assert script.album_id == 8
    assert script.duration == 65
    assert script.track_no == 1
    assert 'toy_ids' not in CreateScriptParam.model_fields
    assert 'sort' not in CreateScriptParam.model_fields


def test_script_album_uses_description_and_track_count() -> None:
    assert 'description' in ScriptAlbum.__table__.columns
    assert 'summary' not in ScriptAlbum.__table__.columns
    assert 'track_count' in ScriptAlbum.__table__.columns
    assert 'script_count' not in ScriptAlbum.__table__.columns


def test_script_detail_accepts_legacy_null_duration_and_track_no() -> None:
    from backend.app.cloud.schema.resource.script import GetScriptDetail

    detail = GetScriptDetail.model_validate({
        'id': 1,
        'album_id': None,
        'title': '历史剧本',
        'content': [{'toy_id': 1, 'text': '你好'}],
        'duration': None,
        'track_no': None,
        'created_time': '2026-09-22T00:00:00+08:00',
    })

    assert detail.duration is None
    assert detail.track_no is None
