from __future__ import annotations

import asyncio
import sys

from typing import Any

import taosrest

from backend.common.log import log
from backend.core.conf import settings


class TDEngineError(RuntimeError):
    """Raised when TDengine operations fail."""


def quote_tdengine_identifier(value: str) -> str:
    """Quote a TDengine identifier."""

    escaped = str(value).replace('`', '``').strip()
    if not escaped:
        raise TDEngineError('TDengine identifier must not be empty')
    return f'`{escaped}`'


def build_create_database_sql(database: str) -> str:
    """Build a CREATE DATABASE statement."""

    return f'CREATE DATABASE IF NOT EXISTS {quote_tdengine_identifier(database)}'


class TDEngineCli:
    """Async TDengine client based on the official taospy REST connector."""

    def __init__(self) -> None:
        self._connections: dict[str | None, Any] = {}
        self._lock = asyncio.Lock()

    @property
    def enabled(self) -> bool:
        return settings.TDENGINE_ENABLED

    @property
    def database(self) -> str:
        return settings.TDENGINE_DATABASE

    @property
    def ready(self) -> bool:
        return bool(self._connections)

    async def init(self) -> None:
        """Initialize the TDengine client."""

        if not self.enabled:
            return

        try:
            await self.ping()
            if settings.TDENGINE_AUTO_CREATE_DATABASE:
                await self.ensure_database()
            log.info(
                'TDengine initialized via taospy-rest at {}://{}:{}/{}',
                settings.TDENGINE_SCHEME,
                settings.TDENGINE_HOST,
                settings.TDENGINE_PORT,
                self.database,
            )
        except Exception as exc:
            log.error('TDengine initialization failed: {}', exc)
            await self.aclose()
            sys.exit()

    async def aclose(self) -> None:
        """Close all cached connections."""

        if not self._connections:
            return

        async with self._lock:
            for connection in self._connections.values():
                await asyncio.to_thread(self._close_connection, connection)
            self._connections.clear()

    async def ping(self) -> None:
        """Verify the TDengine endpoint is reachable."""

        await self.query('SELECT SERVER_VERSION()')

    async def ensure_database(self) -> None:
        """Create the configured database if needed."""

        await self.execute(build_create_database_sql(self.database))

    async def execute(self, sql: str, *, database: str | None = None) -> dict[str, Any]:
        """Execute SQL and return normalized result metadata."""

        async with self._lock:
            connection = await self._get_connection(database=database)
            try:
                return await asyncio.to_thread(self._execute_sql, connection, sql)
            except Exception as exc:
                self._close_connection(connection)
                self._connections.pop(database, None)
                raise TDEngineError(str(exc)) from exc

    async def query(self, sql: str, *, database: str | None = None) -> dict[str, Any]:
        """Alias for execute()."""

        return await self.execute(sql, database=database)

    async def _get_connection(self, *, database: str | None = None) -> Any:
        connection = self._connections.get(database)
        if connection is not None:
            return connection

        connection = await asyncio.to_thread(self._open_connection, database)
        self._connections[database] = connection
        return connection

    @staticmethod
    def _open_connection(database: str | None) -> Any:
        kwargs: dict[str, Any] = {
            'url': f'{settings.TDENGINE_SCHEME}://{settings.TDENGINE_HOST}:{settings.TDENGINE_PORT}',
            'user': settings.TDENGINE_USER,
            'password': settings.TDENGINE_PASSWORD,
            'timeout': settings.TDENGINE_REQUEST_TIMEOUT_SECONDS,
        }
        if database:
            kwargs['database'] = database
        return taosrest.connect(**kwargs)

    @staticmethod
    def _close_connection(connection: Any) -> None:
        close = getattr(connection, 'close', None)
        if callable(close):
            close()

    @staticmethod
    def _execute_sql(connection: Any, sql: str) -> dict[str, Any]:
        cursor = connection.cursor()
        try:
            cursor.execute(sql)
            rows = cursor.fetchall() if hasattr(cursor, 'fetchall') else []
            return {
                'code': 0,
                'rows': len(rows),
                'data': rows,
            }
        finally:
            close = getattr(cursor, 'close', None)
            if callable(close):
                close()


tdengine_client: TDEngineCli = TDEngineCli()
