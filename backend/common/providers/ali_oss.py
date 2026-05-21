# -*- coding: UTF-8 -*-
"""
Aliyun OSS Async Client Wrapper
Author: guhua@jiqid.com
"""

import asyncio
import base64
import hashlib
import hmac
import json

from datetime import datetime, timedelta, timezone as datetime_timezone

import alibabacloud_oss_v2 as oss
import alibabacloud_oss_v2.aio as oss_aio
import oss2

from oss2.credentials import StaticCredentialsProvider

from backend.common.log import log
from backend.common.providers.ali_sts import sts_client
from backend.core.conf import settings


class StaticCredentialProvider(oss.credentials.CredentialsProvider):
    """静态 AK/SK（可以扩展到动态获取）"""

    def __init__(self, access_key_id: str, access_key_secret: str) -> None:
        super().__init__()
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret

    def get_credentials(self) -> oss.credentials.Credentials:
        return oss.credentials.Credentials(self.access_key_id, self.access_key_secret)


class AliOSSClient:
    """
    AliOSS 异步 Client 封装
    """

    CDN_HOST = 'http://media.jiqid.com'  # CDN 域名 避免 https

    def __init__(self, access_key_id: str, access_key_secret: str, bucket: str, region: str = 'cn-hangzhou') -> None:
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret

        self.endpoint = 'https://oss-cn-hangzhou.aliyuncs.com'
        self.bucket = bucket
        self.region = region

        self.provider = StaticCredentialProvider(access_key_id, access_key_secret)

        cfg = oss.config.Config(
            region=self.region,
            credentials_provider=self.provider,
            connect_timeout=5_000,  # ms
        )

        self.client: oss_aio.AsyncClient | None = oss_aio.AsyncClient(cfg)

    async def close(self) -> None:
        """关闭客户端"""
        if self.client:
            await self.client.close()

    async def upload_bytes(self, key: str, data: bytes) -> str:
        """
        上传字节数据到 OSS
        """
        try:
            resp = await self.client.put_object(oss.PutObjectRequest(bucket=self.bucket, key=key, body=data))

            log.info(
                f'[OSS Upload Success] key={key}, status={resp.status_code}, '
                f'etag={resp.etag}, request_id={resp.request_id}'
            )

        except Exception as e:
            log.error(f'[OSS Upload Error] key={key}, error={e!r}')
            return ''

        else:
            return f'{self.CDN_HOST}/{key}'

    def sign_url(self, object_name: str, expires: int = 60, method: str = 'PUT') -> str:
        auth = oss2.ProviderAuthV4(
            StaticCredentialsProvider(self.provider.access_key_id, self.provider.access_key_secret)
        )

        bucket = oss2.Bucket(auth, self.endpoint, self.bucket, region=self.region)
        return bucket.sign_url(method, object_name, expires, slash_safe=True)

    @staticmethod
    def _hmacsha256(key: bytes, data: str) -> bytes:
        return hmac.new(key, data.encode('utf-8'), hashlib.sha256).digest()

    def generate_signature(self) -> dict[str, str]:
        credentials = sts_client.assume_role()
        access_key_id = credentials['access_key_id']
        access_key_secret = credentials['access_key_secret']
        security_token = credentials['security_token']

        now = datetime.now(datetime_timezone.utc)
        expires_at = credentials.get('expiration')
        try:
            policy_expiration = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        except (AttributeError, ValueError):
            policy_expiration = now + timedelta(hours=1)

        if policy_expiration <= now:
            policy_expiration = now + timedelta(minutes=55)

        request_date = now.strftime('%Y%m%d')
        request_time = now.strftime('%Y%m%dT%H%M%SZ')
        expiration = policy_expiration.strftime('%Y-%m-%dT%H:%M:%S.000Z')
        credential = f'{access_key_id}/{request_date}/{self.region}/oss/aliyun_v4_request'

        policy = {
            'expiration': expiration,
            'conditions': [
                {'bucket': self.bucket},
                {'x-oss-signature-version': 'OSS4-HMAC-SHA256'},
                {'x-oss-credential': credential},
                {'x-oss-security-token': security_token},
                {'x-oss-date': request_time},
            ],
        }
        policy_base64 = base64.b64encode(
            json.dumps(policy, separators=(',', ':')).encode('utf-8')
        ).decode('utf-8')

        date_key = self._hmacsha256(f'aliyun_v4{access_key_secret}'.encode('utf-8'), request_date)
        region_key = self._hmacsha256(date_key, self.region)
        service_key = self._hmacsha256(region_key, 'oss')
        signing_key = self._hmacsha256(service_key, 'aliyun_v4_request')
        signature = self._hmacsha256(signing_key, policy_base64).hex()

        return {
            'bucket': self.bucket,
            'region': self.region,
            'host': f'https://{self.bucket}.oss-{self.region}.aliyuncs.com',
            'policy': policy_base64,
            'x-oss-signature-version': 'OSS4-HMAC-SHA256',
            'x-oss-credential': credential,
            'x-oss-date': request_time,
            'x-oss-security-token': security_token,
            'signature': signature,
            'expiration': expiration,
        }


oss_client = AliOSSClient(
    access_key_id=settings.OSS_ACCESS_KEY_ID,
    access_key_secret=settings.OSS_ACCESS_KEY_SECRET,
    bucket=settings.OSS_BUCKET,
    region=settings.OSS_REGION,
)


async def main() -> None:
    key = 'K10/feedback/log/test.log'
    data = b'Hello, OSS!'

    await oss_client.upload_bytes(key, data)
    await oss_client.close()

    rv = oss_client.sign_url(key)
    log.info(rv)
    rv = oss_client.generate_signature()
    log.info(rv)


if __name__ == '__main__':
    asyncio.run(main())
