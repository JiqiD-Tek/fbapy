from importlib import import_module

import pytest
import sqlalchemy as sa

from alembic.migration import MigrationContext
from alembic.operations import Operations
from pydantic import ValidationError

from backend.app.cloud.schema.device.toy import CreateToyParam, UpdateToyParam


@pytest.mark.parametrize('schema', [CreateToyParam, UpdateToyParam])
def test_opening_audio_urls_input(schema: type[CreateToyParam] | type[UpdateToyParam]) -> None:
    params = schema(name='toy', system_prompt='prompt', opening_audio_urls=[' a.mp3 ', 'b.mp3'])
    assert params.model_dump(exclude_unset=True)['opening_audio_urls'] == ['a.mp3', 'b.mp3']
    assert schema(name='toy', system_prompt='prompt', opening_audio_urls=[]).opening_audio_urls == []
    assert schema(name='toy', system_prompt='prompt', opening_audio_urls=None).opening_audio_urls is None


@pytest.mark.parametrize('schema', [CreateToyParam, UpdateToyParam])
@pytest.mark.parametrize('audio_urls', ['a.mp3', ['   '], ['a' * 513], [None]])
def test_invalid_opening_audio_urls(
    schema: type[CreateToyParam] | type[UpdateToyParam],
    audio_urls: object,
) -> None:
    with pytest.raises(ValidationError):
        schema(name='toy', system_prompt='prompt', opening_audio_urls=audio_urls)


def test_update_omission_preserves_existing_audio_urls() -> None:
    assert 'opening_audio_urls' not in UpdateToyParam(name='toy').model_dump(exclude_unset=True)


def test_opening_audio_migration(monkeypatch: pytest.MonkeyPatch) -> None:
    migration = import_module('backend.alembic.versions.20261124_02_toy_opening_audio_urls')
    engine = sa.create_engine('sqlite://')
    original = sa.Table(
        'u_toy',
        sa.MetaData(),
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('intro_audio_url', sa.String(512)),
    )
    audio_url = "https://example.com/hello.mp3?name=O'Reilly"
    with engine.begin() as connection:
        original.create(connection)
        connection.execute(original.insert(), [
            {'id': 1, 'intro_audio_url': audio_url},
            {'id': 2, 'intro_audio_url': None},
            {'id': 3, 'intro_audio_url': ''},
        ])
        monkeypatch.setattr(migration, 'op', Operations(MigrationContext.configure(connection)))
        migration.upgrade()

        migrated = sa.Table('u_toy', sa.MetaData(), autoload_with=connection)
        assert 'intro_audio_url' not in migrated.c
        assert connection.execute(
            sa.select(migrated.c.opening_audio_urls).order_by(migrated.c.id)
        ).scalars().all() == [[audio_url], None, ['']]

        connection.execute(
            migrated.update().where(migrated.c.id == 1).values(opening_audio_urls=[audio_url, 'second.mp3'])
        )
        connection.execute(migrated.update().where(migrated.c.id == 3).values(opening_audio_urls=[]))
        migration.downgrade()

        restored = sa.Table('u_toy', sa.MetaData(), autoload_with=connection)
        assert 'opening_audio_urls' not in restored.c
        assert connection.execute(
            sa.select(restored.c.intro_audio_url).order_by(restored.c.id)
        ).scalars().all() == [audio_url, None, None]
    engine.dispose()
