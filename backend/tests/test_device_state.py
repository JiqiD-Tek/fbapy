from __future__ import annotations

from backend.app.cloud.timeseries.device_state import DeviceStateSnapshot, DeviceStateStore


def test_extract_state_patch() -> None:
    patch = DeviceStateStore._extract_state_patch(
        {
            'online': True,
            'power': 'on',
            'volume': 55,
            'mute': False,
            'player_state': 'playing',
        }
    )

    assert patch == {
        'online': True,
        'power': 'on',
        'volume': 55,
        'mute': False,
        'player_state': 'playing',
    }


def test_merge_snapshot() -> None:
    current = DeviceStateSnapshot(
        did='did-1',
        model='js61',
        updated_at=1.0,
        online=False,
        power='off',
        volume=10,
        mute=True,
        player_state='paused',
    )

    snapshot = DeviceStateStore._merge_snapshot(
        did='did-1',
        model='js61',
        current=current,
        patch={'volume': 55, 'power': 'on'},
        updated_at=2.0,
    )

    assert snapshot.did == 'did-1'
    assert snapshot.model == 'js61'
    assert snapshot.updated_at == 2.0
    assert snapshot.online is False
    assert snapshot.power == 'on'
    assert snapshot.volume == 55
    assert snapshot.mute is True
    assert snapshot.player_state == 'paused'
