# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : build_index.py
@Author  : guhua@jiqid.com
@Date    : 2026/05/22 09:48
"""

from __future__ import annotations

import asyncio
import json

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import sqlalchemy as sa
from backend.common.log import log
from backend.app.cloud.model import CloudAlbum, CloudSong
from backend.database.db import async_db_session

"""
资源类型：1儿歌 2故事 3哄睡
索引：/resource/index.json
资源：/resource/content_type/album_id/song_id.mp3
"""

CONTENT_TYPES: tuple[int, ...] = (1, 2, 3)
DEFAULT_RESOURCE_DIR = Path('D:\\').resolve() / 'resource'
DEFAULT_INDEX_PATH = DEFAULT_RESOURCE_DIR / 'index.json'
DEFAULT_DOWNLOAD_CONCURRENCY = 8
REPLACE_RETRY_COUNT = 5
REPLACE_RETRY_DELAY_SECONDS = 0.2


@dataclass(frozen=True, slots=True)
class ResourceItem:
    content_type: int
    album_id: int
    song_id: int
    track_no: int
    play_url: str


def _get_resource_dir(resource_dir: str | Path | None = None) -> Path:
    return Path(resource_dir) if resource_dir is not None else DEFAULT_RESOURCE_DIR


async def fetch_resource_items() -> list[ResourceItem]:
    stmt = (
        sa.select(
            CloudAlbum.content_type.label('content_type'),
            CloudAlbum.id.label('album_id'),
            CloudSong.id.label('song_id'),
            CloudSong.track_no.label('track_no'),
            CloudSong.play_url.label('play_url'),
        )
        .select_from(CloudAlbum)
        .join(CloudSong, CloudSong.album_id == CloudAlbum.id)
        .where(
            CloudAlbum.status == 1,
            CloudSong.status == 1,
            CloudSong.album_id.is_not(None),
            CloudSong.play_url.is_not(None),
            CloudSong.play_url != '',
            CloudAlbum.content_type.in_(CONTENT_TYPES),
        )
        .order_by(
            CloudAlbum.content_type.asc(),
            CloudAlbum.id.asc(),
            CloudSong.track_no.asc(),
            CloudSong.id.asc(),
        )
    )

    async with async_db_session() as db:
        result = await db.execute(stmt)
        return [
            ResourceItem(
                content_type=int(row['content_type']),
                album_id=int(row['album_id']),
                song_id=int(row['song_id']),
                track_no=int(row['track_no'] or 0),
                play_url=str(row['play_url']).strip(),
            )
            for row in result.mappings()
        ]


def build_index_payload(items: Sequence[ResourceItem]) -> dict[str, list[dict[str, Any]]]:
    album_map: dict[int, dict[int, list[tuple[int, int]]]] = {content_type: {} for content_type in CONTENT_TYPES}

    for item in items:
        album_map[item.content_type].setdefault(item.album_id, []).append((item.track_no, item.song_id))

    return {
        'resource': [
            {
                'content_type': content_type,
                'albums': [
                    {
                        'album_id': album_id,
                        'song_ids': [
                            song_id
                            for _, song_id in sorted(song_items, key=lambda value: (value[0], value[1]))
                        ],
                    }
                    for album_id, song_items in album_map[content_type].items()
                ],
            }
            for content_type in CONTENT_TYPES
        ]
    }


async def build_index() -> dict[str, list[dict[str, Any]]]:
    return build_index_payload(await fetch_resource_items())


async def export_index(output_path: str | Path | None = None) -> Path:
    target_path = Path(output_path) if output_path is not None else DEFAULT_INDEX_PATH
    data = await build_index()

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    return target_path


def _get_song_file_path(resource_dir: Path, item: ResourceItem) -> Path:
    return resource_dir / str(item.content_type) / str(item.album_id) / f'{item.song_id}.mp3'


async def _replace_file_with_retry(source_path: Path, target_path: Path) -> None:
    for attempt in range(REPLACE_RETRY_COUNT):
        try:
            source_path.replace(target_path)
        except PermissionError:
            if attempt == REPLACE_RETRY_COUNT - 1:
                raise
            await asyncio.sleep(REPLACE_RETRY_DELAY_SECONDS)
        else:
            return


async def _download_resource(
        *,
        client: httpx.AsyncClient,
        item: ResourceItem,
        resource_dir: Path,
        semaphore: asyncio.Semaphore,
        overwrite: bool,
) -> str:
    target_path = _get_song_file_path(resource_dir, item)
    if target_path.exists() and not overwrite:
        return 'skipped'

    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_name(f'{target_path.name}.{uuid4().hex}.part')

    try:
        async with semaphore:
            if target_path.exists() and not overwrite:
                return 'skipped'
            async with client.stream('GET', item.play_url) as response:
                response.raise_for_status()
                with temp_path.open('wb') as file_obj:
                    async for chunk in response.aiter_bytes():
                        if chunk:
                            file_obj.write(chunk)
            await _replace_file_with_retry(temp_path, target_path)
    except Exception as exc:
        log.error(f'Failed to download resource: {item.play_url}', exc_info=exc)
        temp_path.unlink(missing_ok=True)
        return 'failed'

    return 'downloaded'


async def dump_resources(
        resource_dir: str | Path | None = None,
        *,
        overwrite: bool = False,
        concurrency: int = DEFAULT_DOWNLOAD_CONCURRENCY,
) -> dict[str, Any]:
    target_dir = _get_resource_dir(resource_dir)
    items = await fetch_resource_items()
    index_path = await export_index(target_dir / 'index.json')

    if not items:
        return {
            'resource_dir': target_dir,
            'index_path': index_path,
            'total': 0,
            'downloaded': 0,
            'skipped': 0,
            'failed': 0,
        }

    semaphore = asyncio.Semaphore(max(concurrency, 1))
    timeout = httpx.Timeout(connect=15.0, read=300.0, write=30.0, pool=30.0)
    limits = httpx.Limits(
        max_connections=max(concurrency, 1),
        max_keepalive_connections=max(concurrency, 1),
        keepalive_expiry=120.0,
    )

    async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
            limits=limits,
            verify=False,
            trust_env=False,
    ) as client:
        results = await asyncio.gather(
            *[
                _download_resource(
                    client=client,
                    item=item,
                    resource_dir=target_dir,
                    semaphore=semaphore,
                    overwrite=overwrite,
                )
                for item in items
            ]
        )

    return {
        'resource_dir': target_dir,
        'index_path': index_path,
        'total': len(items),
        'downloaded': sum(1 for result in results if result == 'downloaded'),
        'skipped': sum(1 for result in results if result == 'skipped'),
        'failed': sum(1 for result in results if result == 'failed'),
    }


def run(output_path: str | Path | None = None) -> Path:
    target_path = asyncio.run(export_index(output_path))
    print(f'已导出资源索引: {target_path}')
    return target_path


def dump(
        resource_dir: str | Path | None = None,
        *,
        overwrite: bool = False,
        concurrency: int = DEFAULT_DOWNLOAD_CONCURRENCY,
) -> dict[str, Any]:
    result = asyncio.run(
        dump_resources(
            resource_dir,
            overwrite=overwrite,
            concurrency=concurrency,
        )
    )
    print(
        '资源下载完成: '
        f"目录={result['resource_dir']} "
        f"总数={result['total']} "
        f"下载={result['downloaded']} "
        f"跳过={result['skipped']} "
        f"失败={result['failed']}"
    )
    return result


def main():
    # run()
    dump()


if __name__ == '__main__':
    main()
