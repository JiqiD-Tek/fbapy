import pytest

from backend.app.cloud.service.resource.huoshan.tts.tts_stream import TTSStreamService
from backend.core.conf import settings


@pytest.mark.parametrize(
    ('speaker', 'expected_resource_id'),
    [
        ('zh_female_xiaohe_uranus_bigtts', 'seed-tts-2.0'),
        ('en_male_corey_emo_v2_mars_bigtts', 'seed-tts-1.0'),
    ],
)
def test_resolve_stream_config_uses_public_voice_resource(
        speaker: str,
        expected_resource_id: str,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, 'BYTES_TTS_STREAM_RESOURCE_ID', 'seed-icl-2.0')

    config = TTSStreamService._resolve_stream_config(speaker)

    assert config['resource_id'] == expected_resource_id


@pytest.mark.parametrize('speaker', ['S_GKcK2x2X1', 'unknown-speaker'])
def test_resolve_stream_config_uses_configured_resource_for_non_public_voice(
        speaker: str,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, 'BYTES_TTS_STREAM_RESOURCE_ID', 'custom-resource-id')

    config = TTSStreamService._resolve_stream_config(speaker)

    assert config['resource_id'] == 'custom-resource-id'
