import asyncio

import pytest

from backend.app.cloud.crud.crud_app import app_dao
from backend.app.cloud.service.app_service import AppService


@pytest.mark.parametrize(
    ('market_code', 'expected'),
    [
        (' cn ', 'cn'),
        ('TW', 'tw'),
        ('global', 'global'),
        ('   ', None),
    ],
)
def test_normalize_market_code(market_code: str, expected: str | None) -> None:
    assert AppService._normalize_market_code(market_code) == expected


def test_empty_market_code_filters_unconfigured_apps() -> None:
    async def run() -> None:
        statement = await app_dao.get_select(
            name=None,
            package_name=None,
            market_code='',
            status=None,
        )

        assert 'market_code IS NULL' in str(statement)

    asyncio.run(run())
