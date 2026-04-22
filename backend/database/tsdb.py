from __future__ import annotations

import asyncio
import sys

from typing import Any

import taosrest

from backend.common.log import log
from backend.core.conf import settings


class TSDBError(RuntimeError):
    """Raised when TSDB operations fail."""


def quote_tsdb_identifier(value: str) -> str:
    """Quote a TSDB identifier."""

    escaped = str(value).replace('`', '``').strip()
    if not escaped:
        raise TSDBError('TSDB identifier must not be empty')
    return f'`{escaped}`'


def build_create_database_sql(database: str) -> str:
    """Build a CREATE DATABASE statement."""

    return f'CREATE DATABASE IF NOT EXISTS {quote_tsdb_identifier(database)}'


class TSDBCli:
    """Async TSDB client based on the official taospy REST connector."""

    def __init__(self) -> None:
        self._connections: dict[str | None, Any] = {}
        self._lock = asyncio.Lock()

    @property
    def enabled(self) -> bool:
        return settings.TSDB_ENABLED

    @property
    def database(self) -> str:
        return settings.TSDB_DATABASE

    @property
    def ready(self) -> bool:
        return bool(self._connections)

    async def init(self) -> None:
        """Initialize the TSDB client."""

        if not self.enabled:
            return

        try:
            await self.ping()
            if settings.TSDB_AUTO_CREATE_DATABASE:
                await self.ensure_database()
            log.info(
                'TSDB initialized via taospy-rest at {}://{}:{}/{}',
                settings.TSDB_SCHEME,
                settings.TSDB_HOST,
                settings.TSDB_PORT,
                self.database,
            )
        except Exception as exc:
            log.error('TSDB initialization failed: {}', exc)
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
        """Verify the TSDB endpoint is reachable."""

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
                raise TSDBError(str(exc)) from exc

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
            'url': f'{settings.TSDB_SCHEME}://{settings.TSDB_HOST}:{settings.TSDB_PORT}',
            'user': settings.TSDB_USER,
            'password': settings.TSDB_PASSWORD,
            'timeout': settings.TSDB_REQUEST_TIMEOUT_SECONDS,
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


tsdb_client: TSDBCli = TSDBCli()
