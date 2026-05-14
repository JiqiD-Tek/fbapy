from __future__ import annotations

import asyncio
import json
import sys

from dataclasses import dataclass
from typing import Any, ClassVar

import taosrest

from backend.common.log import log
from backend.core.conf import settings


class TSDBError(RuntimeError):
    """Raised when TSDB operations fail."""


@dataclass(frozen=True, slots=True)
class TSDBField:
    """Declarative TSDB column/tag definition."""

    name: str
    definition: str
    description: str = ''


def quote_identifier(value: str) -> str:
    """Quote a TSDB identifier."""

    escaped = str(value).replace('`', '``').strip()
    if not escaped:
        raise TSDBError('TSDB identifier must not be empty')
    return f'`{escaped}`'


def quote_value(value: Any) -> str:
    """Quote a TSDB literal value."""

    if value is None:
        return 'NULL'
    if isinstance(value, bool):
        return 'TRUE' if value else 'FALSE'
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, dict | list | tuple):
        value = json.dumps(value, ensure_ascii=False, separators=(',', ':'))

    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"


@dataclass(frozen=True, slots=True)
class TSDBTable:
    """Declarative TSDB table definition backed by a TDengine STABLE."""

    name: str
    columns: tuple[TSDBField, ...]
    tags: tuple[TSDBField, ...]

    @classmethod
    def from_declaration(cls, model_cls: type['TSDBBase']) -> 'TSDBTable':
        table_name = str(getattr(model_cls, '__tablename__', '')).strip()
        columns = tuple(getattr(model_cls, '__columns__', ()))
        tags = tuple(getattr(model_cls, '__tags__', ()))

        if not table_name:
            raise TSDBError(f'{model_cls.__name__} must define __tablename__')
        if not columns:
            raise TSDBError(f'{model_cls.__name__} must define __columns__')
        if not tags:
            raise TSDBError(f'{model_cls.__name__} must define __tags__')

        return cls(name=table_name, columns=columns, tags=tags)

    def create_sql(self) -> str:
        """Build the CREATE STABLE statement for the table."""

        column_sql = ', '.join(f'{quote_identifier(field.name)} {field.definition}' for field in self.columns)
        tag_sql = ', '.join(f'{quote_identifier(field.name)} {field.definition}' for field in self.tags)
        return f'CREATE STABLE IF NOT EXISTS {quote_identifier(self.name)} ({column_sql}) TAGS ({tag_sql})'

    async def create(self, bind: 'TSDBClient', *, database: str | None = None) -> None:
        """Create the table on the target database."""

        await bind.execute(self.create_sql(), database=database or bind.database)

    def insert_sql(
            self,
            *,
            subtable_name: str,
            values: dict[str, Any],
            tags: dict[str, Any],
    ) -> str:
        """Build the INSERT SQL for one subtable row."""

        missing_columns = [field.name for field in self.columns if field.name not in values]
        if missing_columns:
            raise TSDBError(f'TSDB insert missing columns: {", ".join(missing_columns)}')

        missing_tags = [field.name for field in self.tags if field.name not in tags]
        if missing_tags:
            raise TSDBError(f'TSDB insert missing tags: {", ".join(missing_tags)}')

        tag_sql = ', '.join(quote_value(tags[field.name]) for field in self.tags)
        value_sql = ', '.join(quote_value(values[field.name]) for field in self.columns)
        return (
            f'INSERT INTO {quote_identifier(subtable_name)} '
            f'USING {quote_identifier(self.name)} '
            f'TAGS ({tag_sql}) VALUES ({value_sql})'
        )

    async def insert(
            self,
            bind: 'TSDBClient',
            *,
            subtable_name: str,
            values: dict[str, Any],
            tags: dict[str, Any],
            database: str | None = None,
    ) -> None:
        """Insert one row into a TSDB subtable."""

        await bind.execute(
            self.insert_sql(subtable_name=subtable_name, values=values, tags=tags),
            database=database or bind.database,
        )


class TSDBMetaData:
    """In-memory registry for declarative TSDB tables."""

    def __init__(self) -> None:
        self._tables: dict[str, TSDBTable] = {}

    def add_table(self, table: TSDBTable) -> TSDBTable:
        if table.name in self._tables:
            raise TSDBError(f'duplicate TSDB table detected: {table.name}')
        self._tables[table.name] = table
        return table

    async def create_all(self, bind: 'TSDBClient', *, database: str | None = None) -> None:
        target_database = database or bind.database
        for table in self._tables.values():
            await table.create(bind, database=target_database)


class TSDBBase:
    """Declarative TSDB table base class."""

    __abstract__ = True
    metadata: ClassVar[TSDBMetaData] = TSDBMetaData()
    __tablename__: ClassVar[str]
    __columns__: ClassVar[tuple[TSDBField, ...]]
    __tags__: ClassVar[tuple[TSDBField, ...]]
    __table__: ClassVar[TSDBTable]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if cls.__dict__.get('__abstract__', False):
            return

        cls.__table__ = cls.metadata.add_table(TSDBTable.from_declaration(cls))


class TSDBClient:
    """Async TSDB client based on the official taospy REST connector."""

    def __init__(self, *, metadata: TSDBMetaData | None = None) -> None:
        self.metadata = metadata or TSDBBase.metadata
        self._execute_semaphore = asyncio.Semaphore(settings.TSDB_MAX_CONCURRENCY)
        self._ready = False

    @property
    def enabled(self) -> bool:
        return settings.TSDB_ENABLED

    @property
    def database(self) -> str:
        return settings.TSDB_DATABASE

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def endpoint(self) -> str:
        return f'{settings.TSDB_SCHEME}://{settings.TSDB_HOST}:{settings.TSDB_PORT}'

    async def init(self) -> None:
        """Initialize the TSDB client."""

        if not self.enabled:
            return

        try:
            await self.ping()
            await self.create_database()
            await self.create_all()
            self._ready = True
            log.info('TSDB initialized via taospy-rest at {}/{}', self.endpoint, self.database)
        except Exception as exc:
            log.error('TSDB initialization failed: {}', exc)
            await self.aclose()
            sys.exit()

    async def aclose(self) -> None:
        """Reset the TSDB client state."""

        self._ready = False

    async def ping(self) -> None:
        """Verify the TSDB endpoint is reachable."""

        await self.execute('SELECT SERVER_VERSION()')

    async def create_database(self, database: str | None = None) -> None:
        """Create the target database if needed."""

        database_name = quote_identifier(database or self.database)
        await self.execute(f'CREATE DATABASE IF NOT EXISTS {database_name} KEEP {settings.TSDB_KEEP_DAYS}d')
        await self.execute(f'ALTER DATABASE {database_name} KEEP {settings.TSDB_KEEP_DAYS}d')

    async def create_all(self, *, database: str | None = None) -> None:
        """Create all registered tables in the target database."""

        await self.metadata.create_all(self, database=database or self.database)

    async def execute(self, sql: str, *, database: str | None = None) -> dict[str, Any]:
        """Execute SQL and return normalized result metadata."""

        async with self._execute_semaphore:
            try:
                log.debug('TSDB execute: {}', sql)
                return await asyncio.to_thread(
                    self._execute_sql,
                    sql,
                    self.database if database is None else database,
                )
            except Exception as exc:
                log.error('TSDB execute failed: {}', exc)
                raise TSDBError(str(exc)) from exc

    def _open_connection(self, database: str | None) -> Any:
        kwargs: dict[str, Any] = {
            'url': self.endpoint,
            'user': settings.TSDB_USER,
            'password': settings.TSDB_PASSWORD,
            'timeout': settings.TSDB_TIMEOUT_SECONDS,
        }
        if database:
            kwargs['database'] = database
        return taosrest.connect(**kwargs)

    @staticmethod
    def _close_connection(connection: Any) -> None:
        close = getattr(connection, 'close', None)
        if callable(close):
            close()

    def _execute_sql(self, sql: str, database: str | None) -> dict[str, Any]:
        connection = self._open_connection(database)
        try:
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
        finally:
            self._close_connection(connection)


class TSDB:
    """Unified TSDB facade with internal read/write separation."""

    def __init__(self) -> None:
        self._read_client = TSDBClient()
        self._write_client = TSDBClient()

    @property
    def enabled(self) -> bool:
        return settings.TSDB_ENABLED

    @property
    def read_ready(self) -> bool:
        return self._read_client.ready

    @property
    def write_ready(self) -> bool:
        return self._write_client.ready

    async def init(self) -> None:
        await self._read_client.init()
        await self._write_client.init()

    async def aclose(self) -> None:
        await self._write_client.aclose()
        await self._read_client.aclose()

    async def write(self, sql: str, *, database: str | None = None) -> dict[str, Any]:
        return await self._write_client.execute(sql, database=database)

    async def query(self, sql: str, *, database: str | None = None) -> dict[str, Any]:
        return await self._read_client.execute(sql, database=database)


tsdb: TSDB = TSDB()
