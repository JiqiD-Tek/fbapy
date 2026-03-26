# -*- coding: UTF-8 -*-
"""
设备鉴权 Cookie 测试脚本

用法示例:
python backend/test/device_auth_cookie.py --base-url http://127.0.0.1:8000 --mac C41C9C09C981
"""

import argparse
import json
import sys

import httpx


def _derive_did(mac: str, did: str | None) -> str:
    """优先使用入参 did；未提供时按项目规则自动派生。"""
    if did:
        return did

    try:
        from backend.common.security.auth import identity_verifier

        return identity_verifier.derive_credentials(mac=mac)['did']
    except Exception as exc:
        raise RuntimeError(
            '无法自动派生 did，请手动传 --did。'
        ) from exc


def _print_result(title: str, response: httpx.Response) -> None:
    """统一打印响应信息。"""
    print(f'\n[{title}] status={response.status_code}')
    try:
        print(json.dumps(response.json(), ensure_ascii=False, indent=2))
    except Exception:
        print(response.text)


def main() -> int:
    parser = argparse.ArgumentParser(description='测试 terminal 设备鉴权 Cookie 传参')
    parser.add_argument('--base-url', default='http://localhost:8001', help='服务地址')
    parser.add_argument('--path', default='/api/v1/terminal/auth/coze_token', help='测试接口路径')
    parser.add_argument('--method', default='POST', choices=['GET', 'POST'], help='请求方法')
    parser.add_argument('--mac', default='3E:96:10:BA:61:2F', help='设备 MAC')
    parser.add_argument('--did', default='D98BB367386B5B18A815EC31F74B43A6', help='设备 DID，不传则自动派生')
    parser.add_argument('--sn', default='K102501A0100123', help='设备序列号')
    parser.add_argument('--model', default='K11', help='设备型号')
    parser.add_argument('--timeout', type=float, default=10.0, help='请求超时秒数')
    args = parser.parse_args()

    url = f"{args.base_url.rstrip('/')}{args.path}"
    try:
        did = _derive_did(args.mac, args.did)
    except RuntimeError as exc:
        print(str(exc))
        return 2

    print('--- Device Auth Cookie Test ---')
    print(f'url: {url}')
    print(f'mac: {args.mac}')
    print(f'did: {did}')
    print(f'sn: {args.sn}')
    print(f'model: {args.model}')
    print(f'method: {args.method}')

    cookies = {
        'mac': args.mac,
        'did': did,
        'sn': args.sn,
        'model': args.model,
    }

    try:
        # 关闭环境代理，避免 localhost 请求被系统代理转发导致空 502
        with httpx.Client(timeout=args.timeout, trust_env=False) as client:
            # 1) 不带 Cookie，预期失败（例如 code=40003）
            resp_without_cookie = client.request(args.method, url)
            _print_result('without_cookie', resp_without_cookie)

            # 2) 带 Cookie，预期通过
            resp_with_cookie = client.request(args.method, url, cookies=cookies)
            _print_result('with_cookie', resp_with_cookie)
    except httpx.HTTPError as exc:
        print(f'请求失败: {exc}')
        return 3

    return 0


if __name__ == '__main__':
    sys.exit(main())
