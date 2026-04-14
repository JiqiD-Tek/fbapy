import asyncio
import sys
import types
from types import SimpleNamespace

from pytest import MonkeyPatch

fake_ali_oss = types.ModuleType('backend.common.ali_oss')
fake_ali_oss.oss_client = SimpleNamespace(upload_bytes=None)
sys.modules.setdefault('backend.common.ali_oss', fake_ali_oss)

from backend.app.cloud.schema.huoshan import (
    HuoshanStoryBgmInfo,
    HuoshanStorySynthesisParam,
    HuoshanStorySynthesisResult,
    HuoshanVoiceStatus,
)
from backend.app.cloud.service.resource.huoshan.service import HuoshanVoiceService


def test_synthesize_story_returns_task_id_immediately(monkeypatch: MonkeyPatch) -> None:
    calls: dict[str, object] = {}

    class FakeClient:
        async def submit(self, *, payload: dict[str, object], resource_id: str | None = None) -> dict[str, dict[str, str]]:
            calls['submit_payload'] = payload
            return {'data': {'task_id': 'task-123'}}

        async def close(self) -> None:
            return None

    fake_client = FakeClient()

    monkeypatch.setattr(
        HuoshanVoiceService,
        '_get_bgm_song',
        staticmethod(
            lambda db, bgm_song_id: asyncio.sleep(
                0,
                result=SimpleNamespace(
                    id=bgm_song_id,
                    title='Light Music',
                    play_url='https://media.test/bgm.mp3',
                    artist='artist',
                    duration=30,
                ),
            )
        ),
    )
    monkeypatch.setattr(
        HuoshanVoiceService,
        '_get_voice_status',
        lambda self, *, speaker: asyncio.sleep(
            0,
            result=HuoshanVoiceStatus(
                speaker_id=speaker,
                speaker_alias='Kid Voice A',
                state='Active',
            ),
        ),
    )
    monkeypatch.setattr(
        HuoshanVoiceService,
        '_resolve_story_client_config',
        staticmethod(lambda: SimpleNamespace(resource_id='seed-icl-2.0')),
    )
    monkeypatch.setattr(HuoshanVoiceService, '_create_story_client', classmethod(lambda cls: fake_client))

    async def fake_save_story_task_result(cls, result: HuoshanStorySynthesisResult) -> None:
        calls['saved_result'] = result

    monkeypatch.setattr(HuoshanVoiceService, '_save_story_task_result', classmethod(fake_save_story_task_result))

    result = asyncio.run(
        HuoshanVoiceService().synthesize_story(
            db=SimpleNamespace(),
            obj=HuoshanStorySynthesisParam(
                story_content='a story about the moon',
                speaker='speaker-001',
                bgm_song_id=1001,
            ),
        )
    )

    assert result.task_id == 'task-123'
    assert result.task_status == 0
    assert result.is_completed is False
    assert result.download_url is None
    assert result.bgm.play_url == 'https://media.test/bgm.mp3'
    assert calls['saved_result'].task_id == 'task-123'


def test_get_story_synthesis_finalizes_audio_when_task_is_ready(monkeypatch: MonkeyPatch) -> None:
    calls: dict[str, object] = {}
    current_result = HuoshanStorySynthesisResult(
        task_id='task-123',
        speaker='speaker-001',
        speaker_alias='Kid Voice A',
        speaker_state='Active',
        resource_id='seed-icl-2.0',
        audio_format='mp3',
        bgm=HuoshanStoryBgmInfo(
            song_id=1001,
            title='Light Music',
            play_url='https://media.test/bgm.mp3',
            artist='artist',
            duration=30,
        ),
        is_completed=False,
        task_status=0,
    )

    class FakeClient:
        async def query(self, *, task_id: str, resource_id: str | None = None) -> dict[str, dict[str, object]]:
            calls['query_task_id'] = task_id
            return {
                'data': {
                    'task_status': 2,
                    'audio_url': 'https://volc.test/audio.mp3',
                    'sentences': [{'text': 'moon'}],
                }
            }

        async def download_file(self, *, url: str) -> bytes:
            calls['source_audio_url'] = url
            return b'speech-audio'

        async def close(self) -> None:
            return None

    monkeypatch.setattr(HuoshanVoiceService, '_create_story_client', classmethod(lambda cls: FakeClient()))
    monkeypatch.setattr(
        HuoshanVoiceService,
        '_get_story_task_result',
        classmethod(lambda cls, task_id: asyncio.sleep(0, result=current_result)),
    )
    monkeypatch.setattr(
        HuoshanVoiceService,
        '_mix_story_audio',
        classmethod(lambda cls, *, speech_audio, bgm_play_url: asyncio.sleep(0, result=b'mixed-audio')),
    )

    async def fake_upload_story_audio(*, key: str, data: bytes) -> str:
        calls['upload_key'] = key
        calls['upload_data'] = data
        return f'https://media.jiqid.com/{key}'

    async def fake_save_story_task_result(cls, result: HuoshanStorySynthesisResult) -> None:
        calls['saved_result'] = result

    monkeypatch.setattr(HuoshanVoiceService, '_upload_story_audio', staticmethod(fake_upload_story_audio))
    monkeypatch.setattr(HuoshanVoiceService, '_save_story_task_result', classmethod(fake_save_story_task_result))

    result = asyncio.run(HuoshanVoiceService().get_story_synthesis(task_id='task-123'))

    assert calls['query_task_id'] == 'task-123'
    assert calls['source_audio_url'] == 'https://volc.test/audio.mp3'
    assert result.task_status == 2
    assert result.is_completed is True
    assert result.source_audio_url == 'https://volc.test/audio.mp3'
    assert result.download_url == f'https://media.jiqid.com/{calls["upload_key"]}'
    assert result.sentences == [{'text': 'moon'}]
    assert calls['saved_result'].download_url == result.download_url
