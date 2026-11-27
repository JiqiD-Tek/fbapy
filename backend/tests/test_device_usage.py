"""共享用量换算、每日汇总和事件幂等验证。"""

import asyncio
from datetime import date
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError
from sqlalchemy import Integer, MetaData, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.cloud.model import DeviceUsage, DeviceUsageEvent
from backend.app.cloud.schema.device_usage import UpdateDeviceUsageParam
from backend.app.cloud.service.device_usage_service import UsageCalculator, device_usage_service
from backend.common.exception import errors
from backend.core.conf import settings


@pytest.fixture(autouse=True)
def usage_settings(monkeypatch):
    monkeypatch.setattr(settings, 'DEVICE_DAILY_AI_QUOTA', 1_000_000)
    monkeypatch.setattr(settings, 'ASR_CHARACTERS_PER_MINUTE', 300)


def test_conversion_uses_supplied_prices():
    # 识别 300 字约一分钟，模型输入输出共 600 字，合成 300 字。
    assert UsageCalculator.calculate_quantity(asr_characters=300, tts_characters=300) == 161_800
    assert UsageCalculator.calculate_quantity(asr_characters=150, tts_characters=150) == 80_900
    assert UsageCalculator.calculate_quantity(asr_characters=1000, tts_characters=1000) == 539_334
    assert UsageCalculator.calculate_quantity(asr_characters=0, tts_characters=1) == 303


@pytest.mark.parametrize('asr_characters,tts_characters', [(-1, 1), (1, -1)])
def test_calculator_rejects_negative_character_counts(asr_characters, tts_characters):
    with pytest.raises(ValueError):
        UsageCalculator.calculate_quantity(asr_characters=asr_characters, tts_characters=tts_characters)


def test_asr_speed_and_final_rounding(monkeypatch):
    assert UsageCalculator.calculate_quantity(asr_characters=1, tts_characters=1) == 540
    assert UsageCalculator.calculate_quantity(asr_characters=0, tts_characters=0) == 0
    monkeypatch.setattr(settings, 'ASR_CHARACTERS_PER_MINUTE', 200)
    assert UsageCalculator.calculate_quantity(asr_characters=1, tts_characters=1) == 656


@pytest.mark.parametrize('payload', [
    {'event_type': 'CHAT', 'event_key': 'k', 'quantity': 60},
    {'event_type': 'CHAT', 'event_key': 'k', 'asr_characters': -1, 'tts_characters': 1},
    {'event_type': 'CHAT', 'event_key': ' ', 'asr_characters': 1, 'tts_characters': 1},
    {'event_type': 'CHAT', 'event_key': 'k', 'duration_seconds': 60, 'asr_characters': 1, 'tts_characters': 1},
    {'event_type': 'STORY', 'event_key': 'k', 'asr_characters': 1},
    {'event_type': 'STORY', 'event_key': 'k', 'asr_characters': 0, 'tts_characters': 0},
    {'event_type': 'STORY', 'event_key': 'k', 'asr_characters': -1, 'tts_characters': 1},
    {'event_type': 'CHAT', 'event_key': 'k', 'asr_characters': 1, 'tts_characters': -1},
    {'event_type': 'STORY', 'event_key': 'k', 'asr_characters': 1, 'tts_text': '旧参数'},
])
def test_invalid_raw_usage_is_rejected(payload):
    with pytest.raises(ValidationError):
        UpdateDeviceUsageParam.model_validate(payload)


async def create_usage_database():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    metadata = MetaData()
    # SQLite 仅支持 INTEGER 类型自增；生产库仍使用 BIGINT。
    for model in (DeviceUsage, DeviceUsageEvent):
        table = model.__table__.to_metadata(metadata)
        table.c.id.type = Integer()
    async with engine.begin() as connection:
        await connection.run_sync(metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


def test_shared_daily_total_and_idempotent_events():
    async def run():
        engine, sessions = await create_usage_database()
        today, tomorrow = date(2026, 11, 27), date(2026, 11, 28)
        try:
            async with sessions.begin() as db:
                assert await device_usage_service.record_usage(
                    db=db, did='d1', event_type='CHAT', event_key='chat',
                    asr_characters=300, tts_characters=300, usage_date=today,
                )
                assert not await device_usage_service.record_usage(
                    db=db, did='d1', event_type='CHAT', event_key='chat',
                    asr_characters=300, tts_characters=300, usage_date=today,
                )
                assert await device_usage_service.record_usage(
                    db=db, did='d1', event_type='STORY', event_key='story',
                    asr_characters=1000, tts_characters=1000, usage_date=today,
                )
                assert not await device_usage_service.record_usage(
                    db=db, did='d1', event_type='STORY', event_key='story',
                    asr_characters=1000, tts_characters=1000, usage_date=today,
                )
                await device_usage_service.record_usage(
                    db=db, did='d1', event_type='CHAT', event_key='tomorrow',
                    asr_characters=150, tts_characters=150, usage_date=tomorrow,
                )
                await device_usage_service.record_usage(
                    db=db, did='d2', event_type='CHAT', event_key='other-device',
                    asr_characters=150, tts_characters=150, usage_date=today,
                )
            async with sessions() as db:
                usage = await device_usage_service.get_daily_usage(db=db, did='d1', usage_date=today)
                assert usage.quantity == 701_134
                quota = device_usage_service.build_quota_result(did='d1', usage_date=today, usage=usage)
                assert quota['remaining_quantity'] == 298_866
                next_day = await device_usage_service.get_daily_usage(db=db, did='d1', usage_date=tomorrow)
                assert next_day.quantity == 80_900
                assert (await db.scalar(select(func.count()).select_from(DeviceUsageEvent))) == 4
                assert (await db.scalar(select(func.count()).select_from(DeviceUsage))) == 3
        finally:
            await engine.dispose()
    asyncio.run(run())


def test_actual_consumption_is_recorded_when_quota_is_exceeded(monkeypatch):
    monkeypatch.setattr(settings, 'DEVICE_DAILY_AI_QUOTA', 100)

    async def run():
        engine, sessions = await create_usage_database()
        try:
            async with sessions.begin() as db:
                await device_usage_service.ensure_quota_available(db=db, did='d1')
                await device_usage_service.record_usage(
                    db=db, did='d1', event_type='CHAT', event_key='k', asr_characters=1, tts_characters=1,
                )
            async with sessions() as db:
                usage = await device_usage_service.get_daily_usage(db=db, did='d1')
                quota = device_usage_service.build_quota_result(did='d1', usage_date=usage.usage_date, usage=usage)
                assert quota['quantity'] == 540
                assert quota['remaining_quantity'] == 0
                with pytest.raises(errors.RequestError):
                    await device_usage_service.ensure_quota_available(db=db, did='d1')
        finally:
            await engine.dispose()
    asyncio.run(run())


@pytest.mark.parametrize('succeed', [True, False])
def test_toy_story_records_characters_only_after_success(monkeypatch, succeed):
    from backend.app.cloud.schema.resource.huoshan import HuoshanToyStoryScriptResult, HuoshanToyStoryToyInfo
    from backend.app.cloud.service.resource.huoshan import service as huoshan

    async def run():
        engine, sessions = await create_usage_database()
        service = huoshan.HuoshanVoiceService()
        result = HuoshanToyStoryScriptResult(
            task_id='story-task', toy_ids=[1], text='测试主题', model='test',
            toys=[HuoshanToyStoryToyInfo(toy_id=1, name='玩偶')],
            device_did='original-device', baby_id=None, is_completed=False, task_status=1,
        )
        prompts = []

        async def stream(messages, **kwargs):
            prompts.extend(messages)
            yield '[1]你好\n'
            if not succeed:
                raise RuntimeError('模拟生成失败')
            yield '[1]再见'

        monkeypatch.setattr(huoshan, 'async_db_session', sessions)
        monkeypatch.setattr(huoshan.doubao_provider, 'stream_chat', stream)
        monkeypatch.setattr(huoshan.tts_cache, 'create_new_request', AsyncMock(return_value='token'))
        monkeypatch.setattr(service, 'get_toy_story_script', AsyncMock(return_value=result))
        monkeypatch.setattr(service, '_save_toy_story_script_task_result', AsyncMock())
        monkeypatch.setattr(service, '_save_toy_story_script', AsyncMock())
        try:
            completed = await service._process_toy_story_script('story-task')
            await asyncio.sleep(0)
            async with sessions() as db:
                usage = await device_usage_service.get_daily_usage(db=db, did='original-device')
                if succeed:
                    assert completed.is_completed
                    assert usage is not None
                    expected_quantity = UsageCalculator.calculate_quantity(
                        asr_characters=len(result.text), tts_characters=4,
                    )
                    assert usage.quantity == expected_quantity
                    event = await db.scalar(select(DeviceUsageEvent))
                    assert event.event_key == 'story-task'
                    assert event.quantity == expected_quantity
                else:
                    assert completed.task_status == huoshan.STORY_TASK_STATUS_FAILED
                    assert usage is None
                    assert (await db.scalar(select(func.count()).select_from(DeviceUsageEvent))) == 0
        finally:
            await engine.dispose()

    asyncio.run(run())
