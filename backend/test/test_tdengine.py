import pytest

from backend.database.tdengine import TDEngineCli, TDEngineError, build_create_database_sql, quote_tdengine_identifier


def test_quote_tdengine_identifier() -> None:
    assert quote_tdengine_identifier('fba') == '`fba`'
    assert quote_tdengine_identifier('f`ba') == '`f``ba`'


def test_quote_tdengine_identifier_rejects_empty_values() -> None:
    with pytest.raises(TDEngineError):
        quote_tdengine_identifier('   ')


def test_build_create_database_sql() -> None:
    assert build_create_database_sql('fba') == 'CREATE DATABASE IF NOT EXISTS `fba`'


@pytest.mark.anyio
async def test_ensure_database_executes_create_sql(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def fake_execute(self: TDEngineCli, sql: str, *, database: str | None = None) -> dict[str, object]:
        captured['sql'] = sql
        captured['database'] = database
        return {'code': 0}

    monkeypatch.setattr(TDEngineCli, 'execute', fake_execute)

    client = TDEngineCli()
    await client.ensure_database()

    assert captured == {
        'sql': 'CREATE DATABASE IF NOT EXISTS `fba`',
        'database': None,
    }
