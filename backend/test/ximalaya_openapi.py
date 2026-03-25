from __future__ import annotations

import importlib.util
import sys
import types

from pathlib import Path
from typing import Any


def load_ximalaya_package() -> types.ModuleType:
    project_root = Path(__file__).resolve().parents[2]
    backend_dir = project_root / 'backend'
    app_dir = backend_dir / 'app'
    iot_dir = app_dir / 'iot'
    service_dir = iot_dir / 'service'
    cloud_dir = service_dir / 'cloud'
    package_dir = cloud_dir / 'ximalaya'
    package_name = 'backend.app.iot.service.cloud.ximalaya'
    package_init = package_dir / '__init__.py'

    for name in tuple(sys.modules):
        if name in {
            'backend',
            'backend.app',
            'backend.app.iot',
            'backend.app.iot.service',
            'backend.app.iot.service.cloud',
            'backend.common',
            'backend.common.http_client',
        } or name.startswith('backend.app.iot.service.cloud.ximalaya'):
            sys.modules.pop(name, None)

    backend_pkg = types.ModuleType('backend')
    backend_pkg.__path__ = [str(backend_dir)]  # type: ignore[attr-defined]

    app_pkg = types.ModuleType('backend.app')
    app_pkg.__path__ = [str(app_dir)]  # type: ignore[attr-defined]

    iot_pkg = types.ModuleType('backend.app.iot')
    iot_pkg.__path__ = [str(iot_dir)]  # type: ignore[attr-defined]

    service_pkg = types.ModuleType('backend.app.iot.service')
    service_pkg.__path__ = [str(service_dir)]  # type: ignore[attr-defined]

    cloud_pkg = types.ModuleType('backend.app.iot.service.cloud')
    cloud_pkg.__path__ = [str(cloud_dir)]  # type: ignore[attr-defined]

    common_pkg = types.ModuleType('backend.common')
    common_pkg.__path__ = [str(backend_dir / 'common')]  # type: ignore[attr-defined]

    http_client_mod = types.ModuleType('backend.common.http_client')

    class DummyHTTPClient:
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

        async def close(self) -> None:
            return None

    http_client_mod.HTTPClient = DummyHTTPClient

    sys.modules['backend'] = backend_pkg
    sys.modules['backend.app'] = app_pkg
    sys.modules['backend.app.iot'] = iot_pkg
    sys.modules['backend.app.iot.service'] = service_pkg
    sys.modules['backend.app.iot.service.cloud'] = cloud_pkg
    sys.modules['backend.common'] = common_pkg
    sys.modules['backend.common.http_client'] = http_client_mod

    spec = importlib.util.spec_from_file_location(
        package_name,
        package_init,
        submodule_search_locations=[str(package_dir)],
    )
    assert spec and spec.loader

    module = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = module
    spec.loader.exec_module(module)
    return module


MODULE = load_ximalaya_package()
XimalayaClientConfig = MODULE.XimalayaClientConfig
XimalayaOpenAPIClient = MODULE.XimalayaOpenAPIClient


def build_client() -> Any:
    return XimalayaOpenAPIClient(
        XimalayaClientConfig(
            app_key='demo-app',
            app_secret='demo-secret',
            sn='sn-001',
            device_id='device-001',
            version='1.0.0',
        )
    )


def test_sign_matches_expected_doc_style_algorithm() -> None:
    client = build_client()

    params = client.build_signed_params(
        {'q': '\u5e78\u798f\u6e9c+7'},
        nonce='nonce-001',
        timestamp=1710000000000,
    )

    assert params['sig'] == 'c907eebe1033ca2c94417952ae3646cb'


def test_build_signed_params_serializes_bool_and_json_payloads() -> None:
    client = build_client()

    params = client.build_signed_params(
        {
            'contains_paid': False,
            'play_history_records': [
                {
                    'content_type': 1,
                    'album_id': 5203901,
                    'track_id': 47430378,
                    'break_second': 3,
                }
            ],
        },
        nonce='nonce-002',
        timestamp=1710000000001,
    )

    assert params['contains_paid'] == 'false'
    assert params['play_history_records'] == (
        '[{"content_type":1,"album_id":5203901,"track_id":47430378,"break_second":3}]'
    )
    assert params['sig']
