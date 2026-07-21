from __future__ import annotations

import asyncio

from types import SimpleNamespace

import pytest

from backend.app.cloud.schema.resource.huoshan import (
    HuoshanRoleStoryRoleInfo,
    HuoshanRoleStoryScriptParam,
    HuoshanRoleStoryScriptTaskResult,
    HuoshanStorySynthesisParam,
    HuoshanStorySynthesisResult,
)
from backend.app.cloud.service.resource.huoshan import service as huoshan_service_module
from backend.app.cloud.service.resource.huoshan.service import HuoshanVoiceService
from backend.common.providers.doubao import DEFAULT_DOUBAO_LITE_MODEL


def test_huoshan_role_story_script_param_normalizes_input() -> None:
    obj = HuoshanRoleStoryScriptParam(role_ids=[1, 1, 2], text='  no lead role  ')

    assert obj.role_ids == [1, 2]
    assert obj.text == 'no lead role'


def test_submit_role_story_script_saves_task_and_starts_processing(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    service = HuoshanVoiceService()

    async def get_roles_by_ids_stub(*, db: object, role_ids: list[int]) -> list[SimpleNamespace]:
        captured['db'] = db
        captured['role_ids'] = role_ids
        return [
            SimpleNamespace(id=1, name='A', summary='role A', system_prompt='calm'),
            SimpleNamespace(id=2, name='B', summary='role B', system_prompt='bright'),
        ]

    async def save_stub(result: HuoshanRoleStoryScriptTaskResult) -> None:
        captured['saved_result'] = result

    monkeypatch.setattr(huoshan_service_module.cloud_role_service, 'get_roles_by_ids', get_roles_by_ids_stub)
    monkeypatch.setattr(huoshan_service_module.uuid, 'uuid4', lambda: SimpleNamespace(hex='task-role-story'))
    monkeypatch.setattr(service, '_save_role_story_script_task_result', save_stub)
    monkeypatch.setattr(service, '_start_role_story_script_processing', lambda task_id: captured.setdefault('started_task_id', task_id))

    result = asyncio.run(
        service.submit_role_story_script(
            db=object(),
            obj=HuoshanRoleStoryScriptParam(role_ids=[1, 2], text='No lead role, create a random story'),
        )
    )

    assert captured['role_ids'] == [1, 2]
    assert result.task_id == 'task-role-story'
    assert result.role_ids == [1, 2]
    assert result.text == 'No lead role, create a random story'
    assert result.model == DEFAULT_DOUBAO_LITE_MODEL
    assert result.lines == []
    assert result.is_completed is False
    assert result.task_status == huoshan_service_module.STORY_TASK_STATUS_PROCESSING
    assert result.error_message is None

    saved_result = captured['saved_result']
    assert isinstance(saved_result, HuoshanRoleStoryScriptTaskResult)
    assert [role.role_id for role in saved_result.roles] == [1, 2]
    assert captured['started_task_id'] == 'task-role-story'


def test_process_role_story_script_completes_task(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    service = HuoshanVoiceService()
    store = {
        'task-role-story': HuoshanRoleStoryScriptTaskResult(
            task_id='task-role-story',
            role_ids=[1, 2],
            text='Create a balanced random story',
            model=DEFAULT_DOUBAO_LITE_MODEL,
            lines=[],
            is_completed=False,
            task_status=huoshan_service_module.STORY_TASK_STATUS_PROCESSING,
            error_message=None,
            roles=[
                HuoshanRoleStoryRoleInfo(role_id=1, name='A', summary='role A', system_prompt='calm'),
                HuoshanRoleStoryRoleInfo(role_id=2, name='B', summary='role B', system_prompt='bright'),
            ],
        )
    }

    async def stream_chat_stub(messages: list[dict[str, str]], **kwargs: object):
        captured['messages'] = messages
        captured['kwargs'] = kwargs
        yield '[1]A says'
        yield ' hi\n[2]B says hi'

    monkeypatch.setattr(huoshan_service_module.doubao_provider, 'stream_chat', stream_chat_stub)
    monkeypatch.setattr(service, '_get_role_story_script_task_result', lambda task_id: asyncio.sleep(0, result=store[task_id]))

    save_history: list[list[str]] = []

    async def save_stub(result: HuoshanRoleStoryScriptTaskResult) -> None:
        store[result.task_id] = result
        save_history.append([item.text for item in result.lines])

    monkeypatch.setattr(service, '_save_role_story_script_task_result', save_stub)

    result = asyncio.run(service._process_role_story_script('task-role-story'))

    assert captured['kwargs'] == {
        'model_name': DEFAULT_DOUBAO_LITE_MODEL,
        'reasoning_effort': 'minimal',
        'temperature': 0.8,
    }
    assert [item.role_id for item in result.lines] == [1, 2]
    assert [item.text for item in result.lines] == ['A says hi', 'B says hi']
    assert result.is_completed is True
    assert result.task_status == huoshan_service_module.STORY_TASK_STATUS_COMPLETED
    assert store['task-role-story'].is_completed is True
    assert save_history[0] == ['A says hi']
    assert save_history[-1] == ['A says hi', 'B says hi']


def test_process_role_story_script_marks_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    service = HuoshanVoiceService()
    store = {
        'task-role-story': HuoshanRoleStoryScriptTaskResult(
            task_id='task-role-story',
            role_ids=[1, 2],
            text='Create a random story',
            model=DEFAULT_DOUBAO_LITE_MODEL,
            lines=[],
            is_completed=False,
            task_status=huoshan_service_module.STORY_TASK_STATUS_PROCESSING,
            error_message=None,
            roles=[
                HuoshanRoleStoryRoleInfo(role_id=1, name='A', summary='role A', system_prompt='calm'),
                HuoshanRoleStoryRoleInfo(role_id=2, name='B', summary='role B', system_prompt='bright'),
            ],
        )
    }

    async def stream_chat_stub(messages: list[dict[str, str]], **kwargs: object):
        yield '[3]unexpected'

    monkeypatch.setattr(huoshan_service_module.doubao_provider, 'stream_chat', stream_chat_stub)
    monkeypatch.setattr(service, '_get_role_story_script_task_result', lambda task_id: asyncio.sleep(0, result=store[task_id]))

    async def save_stub(result: HuoshanRoleStoryScriptTaskResult) -> None:
        store[result.task_id] = result

    monkeypatch.setattr(service, '_save_role_story_script_task_result', save_stub)

    result = asyncio.run(service._process_role_story_script('task-role-story'))

    assert result.is_completed is False
    assert result.task_status == huoshan_service_module.STORY_TASK_STATUS_FAILED
    assert 'unexpected role ID' in str(result.error_message)


def test_get_role_story_script_returns_public_result(monkeypatch: pytest.MonkeyPatch) -> None:
    service = HuoshanVoiceService()
    cached_result = HuoshanRoleStoryScriptTaskResult(
        task_id='task-role-story',
        role_ids=[1, 2],
        text='Create a random story',
        model=DEFAULT_DOUBAO_LITE_MODEL,
        lines=[],
        is_completed=False,
        task_status=huoshan_service_module.STORY_TASK_STATUS_PROCESSING,
        error_message=None,
        roles=[
            HuoshanRoleStoryRoleInfo(role_id=1, name='A', summary='role A', system_prompt='calm'),
            HuoshanRoleStoryRoleInfo(role_id=2, name='B', summary='role B', system_prompt='bright'),
        ],
    )

    monkeypatch.setattr(service, '_get_role_story_script_task_result', lambda task_id: asyncio.sleep(0, result=cached_result))

    result = asyncio.run(service.get_role_story_script(task_id='task-role-story'))

    assert result.task_id == 'task-role-story'
    assert result.role_ids == [1, 2]
    assert not hasattr(result, 'roles')


def test_synthesize_story_allows_missing_bgm(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    service = HuoshanVoiceService()

    class DummyClient:
        async def submit(self, payload: dict[str, object]) -> dict[str, object]:
            captured['submit_payload'] = payload
            return {'data': {'task_id': 'story-task-1'}, '_request_id': 'req-1'}

        async def close(self) -> None:
            captured['closed'] = True

    monkeypatch.setattr(service, '_get_bgm_song', lambda db, bgm_song_id: (_ for _ in ()).throw(AssertionError('should not load bgm')))
    monkeypatch.setattr(huoshan_service_module, 'get_public_voice', lambda speaker: SimpleNamespace(id=speaker, name='Voice', resource_id='res-1'))
    monkeypatch.setattr(service, '_resolve_story_client_config', lambda speaker, resource_id=None: SimpleNamespace(resource_id='res-1'))
    monkeypatch.setattr(service, '_create_story_client', lambda speaker, resource_id=None: DummyClient())
    monkeypatch.setattr(service, '_save_story_synthesis_task_result', lambda result: asyncio.sleep(0, result=None))
    monkeypatch.setattr(service, '_start_story_synthesis_processing', lambda task_id: captured.setdefault('started_task_id', task_id))

    result = asyncio.run(
        service.synthesize_story(
            db=object(),
            obj=HuoshanStorySynthesisParam(
                story_content='story',
                speaker='speaker-1',
                bgm_song_id=None,
            ),
        )
    )

    assert result.task_id == 'story-task-1'
    assert result.bgm is None
    assert result.bgm_volume == 0
    assert captured['started_task_id'] == 'story-task-1'


def test_finalize_story_synthesis_without_bgm_skips_mix(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    service = HuoshanVoiceService()
    current_result = HuoshanStorySynthesisResult(
        task_id='story-task-1',
        submit_request_id='req-1',
        speaker='speaker-1',
        speaker_alias='Voice',
        speaker_state=None,
        resource_id='res-1',
        audio_format='mp3',
        bgm=None,
        bgm_volume=0,
        speech_rate=0,
        loudness_rate=0,
        is_completed=False,
        task_status=huoshan_service_module.STORY_TASK_STATUS_PROCESSING,
        source_audio_url='https://example.com/source.mp3',
    )

    class DummyClient:
        async def download_file(self, url: str) -> bytes:
            captured['source_audio_url'] = url
            return b'speech-audio'

    async def upload_stub(*, key: str, data: bytes) -> str:
        captured['upload_key'] = key
        captured['upload_data'] = data
        return 'https://example.com/final.mp3'

    async def mix_stub(**kwargs):
        raise AssertionError('should not mix audio without bgm')

    monkeypatch.setattr(service, '_upload_story_audio', upload_stub)
    monkeypatch.setattr(service, '_mix_story_audio', mix_stub)
    monkeypatch.setattr(service, '_build_story_oss_key', lambda task_id: 'story.mp3')

    result = asyncio.run(
        service._finalize_story_synthesis(
            current_result=current_result,
            client=DummyClient(),
        )
    )

    assert captured['source_audio_url'] == 'https://example.com/source.mp3'
    assert captured['upload_data'] == b'speech-audio'
    assert result.is_completed is True
    assert result.download_url == 'https://example.com/final.mp3'
