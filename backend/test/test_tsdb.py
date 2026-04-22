import pytest

from backend.database.tsdb import TSDBCli, TSDBError, build_create_database_sql, quote_tsdb_identifier


def test_quote_tsdb_identifier() -> None:
    assert quote_tsdb_identifier('fba') == '`fba`'
    assert quote_tsdb_identifier('f`ba') == '`f``ba`'


def test_quote_tsdb_identifier_rejects_empty_values() -> None:
    with pytest.raises(TSDBError):
        quote_tsdb_identifier('   ')


def test_build_create_database_sql() -> None:
    assert build_create_database_sql('fba') == 'CREATE DATABASE IF NOT EXISTS `fba`'


@pytest.mark.anyio
async def test_ensure_database_executes_create_sql(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def fake_execute(self: TSDBCli, sql: str, *, database: str | None = None) -> dict[str, object]:
        captured['sql'] = sql
        captured['database'] = database
        return {'code': 0}

    monkeypatch.setattr(TSDBCli, 'execute', fake_execute)

    client = TSDBCli()
    await client.ensure_database()

    assert captured == {
        'sql': 'CREATE DATABASE IF NOT EXISTS `fba`',
        'database': None,
    }
