import asyncio
import json

import pytest
import sqlalchemy as sa

from pydantic import ValidationError
from sqlalchemy.dialects import postgresql

from backend.app.cloud.crud.resource.crud_script import script_dao
from backend.app.cloud.model import Script
from backend.app.cloud.schema.resource.script import UpdateScriptParam
from backend.app.cloud.schema.resource.script_album import UpdateScriptAlbumParam
from backend.core.conf import settings


@pytest.mark.parametrize('field', ['resource_type', 'content', 'version', 'duration', 'track_no', 'status'])
def test_script_update_rejects_explicit_null(field: str) -> None:
    with pytest.raises(ValidationError):
        UpdateScriptParam(**{field: None})


@pytest.mark.parametrize('field', ['resource_type', 'status'])
def test_album_update_rejects_explicit_null(field: str) -> None:
    with pytest.raises(ValidationError):
        UpdateScriptAlbumParam(**{field: None})


def test_updates_allow_omitted_fields_and_clearing_nullable_fields() -> None:
    assert UpdateScriptParam(title='new').model_dump(exclude_unset=True) == {'title': 'new'}
    assert UpdateScriptAlbumParam(title='new').model_dump(exclude_unset=True) == {'title': 'new'}
    assert UpdateScriptParam(album_id=None, content_types=None).model_dump(exclude_unset=True) == {
        'album_id': None, 'content_types': None,
    }
    assert UpdateScriptParam(resource_type=0, status=0).model_dump(exclude_unset=True) == {
        'resource_type': 0, 'status': 0,
    }


def test_script_update_rejects_empty_content() -> None:
    with pytest.raises(ValidationError):
        UpdateScriptParam(content=[])


def test_content_type_filter_matches_all_requested_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, 'DATABASE_TYPE', 'mysql')
    stmt = asyncio.run(script_dao.get_select(title=None, author=None, status=None, content_types=[1, 3]))
    engine = sa.create_engine('sqlite://')
    table = sa.Table(
        'u_script', sa.MetaData(),
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('content_types', sa.JSON),
    )
    with engine.begin() as connection:
        connection.connection.driver_connection.create_function(
            'JSON_CONTAINS', 2,
            lambda document, values: int(set(json.loads(values)).issubset(json.loads(document) or [])),
        )
        table.create(connection)
        connection.execute(table.insert(), [
            {'id': 1, 'content_types': [3, 1, 2]},
            {'id': 2, 'content_types': [1]},
            {'id': 3, 'content_types': None},
            {'id': 4, 'content_types': [1, 3]},
        ])
        assert connection.execute(stmt.with_only_columns(Script.id)).scalars().all() == [4, 1]
    engine.dispose()


def test_content_type_filter_compiles_for_postgresql(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, 'DATABASE_TYPE', 'postgresql')
    stmt = asyncio.run(script_dao.get_select(title=None, author=None, status=None, content_types=[1, 3]))
    compiled = stmt.compile(dialect=postgresql.dialect())
    assert '@>' in str(compiled)
    assert [1, 3] in compiled.params.values()
