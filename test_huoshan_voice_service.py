from __future__ import annotations

import asyncio

from types import SimpleNamespace

import pytest

from backend.app.cloud.schema.resource.huoshan import (
    HuoshanRoleStoryRoleInfo,
    HuoshanRoleStoryScriptParam,
    HuoshanRoleStoryScriptTaskResult,
)
from backend.app.cloud.service.resource.huoshan import service as huoshan_service_module
from backend.app.cloud.service.resource.huoshan.service import HuoshanVoiceService
from backend.common.providers.doubao import DEFAULT_DOUBAO_STORY_MODEL


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
    assert result.model == DEFAULT_DOUBAO_STORY_MODEL
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
            model=DEFAULT_DOUBAO_STORY_MODEL,
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
        'model_name': DEFAULT_DOUBAO_STORY_MODEL,
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
            model=DEFAULT_DOUBAO_STORY_MODEL,
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
        model=DEFAULT_DOUBAO_STORY_MODEL,
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
