import asyncio
from types import SimpleNamespace

import pytest

from backend.app.cloud.api.v1.resource.huoshan import submit_huoshan_toy_story_script
from backend.app.cloud.schema.resource.huoshan import HuoshanToyStoryScriptParam
from backend.app.cloud.schema.user import DeviceAuthParam
from backend.app.cloud.service.resource.huoshan.service import huoshan_voice_service
from backend.common.exception import errors


def _build_param() -> HuoshanToyStoryScriptParam:
    return HuoshanToyStoryScriptParam(toy_ids=[1], text='生成一个睡前故事')


def test_submit_api_passes_device_did_to_service(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def fake_submit(*, db, obj, device_did: str | None):
        captured.update(db=db, obj=obj, device_did=device_did)
        return None

    monkeypatch.setattr(huoshan_voice_service, 'submit_toy_story_script', fake_submit)
    obj = _build_param()
    asyncio.run(
        submit_huoshan_toy_story_script(
            db='db-session',
            obj=obj,
            auth_ctx=DeviceAuthParam(
                mac='00:11:22:33:44:55',
                did='device-did',
                sn='SN-001',
                model='FBA-TOY',
            ),
        )
    )

    assert captured == {'db': 'db-session', 'obj': obj, 'device_did': 'device-did'}


def test_submit_api_passes_none_for_platform_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def fake_submit(*, db, obj, device_did: str | None):  # noqa: ARG001
        captured['device_did'] = device_did
        return None

    monkeypatch.setattr(huoshan_voice_service, 'submit_toy_story_script', fake_submit)
    asyncio.run(
        submit_huoshan_toy_story_script(
            db='db-session',
            obj=_build_param(),
            auth_ctx=SimpleNamespace(id=7, is_staff=True),
        )
    )

    assert captured['device_did'] is None


def test_submit_service_rejects_unbound_device(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_by_device_did(*, db, did: str):  # noqa: ARG001
        return None

    monkeypatch.setattr(
        'backend.app.cloud.service.resource.huoshan.service.baby_service.get_by_device_did',
        fake_get_by_device_did,
    )

    with pytest.raises(errors.RequestError, match='当前设备未绑定宝宝'):
        asyncio.run(
            huoshan_voice_service.submit_toy_story_script(
                db='db-session',
                obj=_build_param(),
                device_did='device-did',
            )
        )


def test_submit_service_fixes_bound_baby_on_task(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_by_device_did(*, db, did: str):
        assert db == 'db-session'
        assert did == 'device-did'
        return SimpleNamespace(id=42)

    async def fake_get_toys_by_ids(*, db, toy_ids: list[int]):
        assert db == 'db-session'
        assert toy_ids == [1]
        return [
            SimpleNamespace(
                id=1,
                name='小熊',
                summary='勇敢的小熊',
                system_prompt='温柔地讲故事',
                voice_id='voice-1',
                voice_name='小熊声音',
                speech_rate=0,
                loudness_rate=0,
            )
        ]

    async def fake_save(result) -> None:  # noqa: ARG001
        return None

    monkeypatch.setattr(
        'backend.app.cloud.service.resource.huoshan.service.baby_service.get_by_device_did',
        fake_get_by_device_did,
    )
    monkeypatch.setattr(
        'backend.app.cloud.service.resource.huoshan.service.toy_service.get_toys_by_ids',
        fake_get_toys_by_ids,
    )
    monkeypatch.setattr(huoshan_voice_service, '_save_toy_story_script_task_result', fake_save)
    monkeypatch.setattr(huoshan_voice_service, '_start_toy_story_script_processing', lambda task_id: None)

    result = asyncio.run(
        huoshan_voice_service.submit_toy_story_script(
            db='db-session',
            obj=_build_param(),
            device_did='device-did',
        )
    )

    assert result.baby_id == 42
