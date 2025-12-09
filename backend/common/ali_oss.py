# -*- coding: UTF-8 -*-
"""
Aliyun OSS Async Client Wrapper
Author: guhua@jiqid.com
"""

import asyncio
from typing import Optional

import alibabacloud_oss_v2 as oss
import alibabacloud_oss_v2.aio as oss_aio

from backend.common.log import log
from backend.core.conf import settings


class StaticCredentialProvider(oss.credentials.CredentialsProvider):
    """ 静态 AK/SK（可以扩展到动态获取） """

    def __init__(self, access_key_id: str, access_key_secret: str):
        super().__init__()
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret

    def get_credentials(self):
        return oss.credentials.Credentials(
            self.access_key_id,
            self.access_key_secret
        )


class AliOSSClient:
    """
    AliOSS 异步 Client 封装
    """

    def __init__(
            self,
            access_key_id: str,
            access_key_secret: str,
            bucket: str,
            region: str = "cn-hangzhou"
    ):
        self.bucket = bucket
        self.region = region

        provider = StaticCredentialProvider(access_key_id, access_key_secret)

        cfg = oss.config.Config(
            region=self.region,
            credentials_provider=provider,
            connect_timeout=5_000,  # ms
        )

        self.client: Optional[oss_aio.AsyncClient] = oss_aio.AsyncClient(cfg)

    async def close(self):
        """ 关闭客户端 """
        if self.client:
            await self.client.close()

    async def upload_bytes(self, key: str, data: bytes) -> str:
        """
        上传字节数据到 OSS
        """
        try:
            resp = await self.client.put_object(
                oss.PutObjectRequest(
                    bucket=self.bucket,
                    key=key,
                    body=data
                )
            )

            log.info(
                f"[OSS Upload Success] key={key}, status={resp.status_code}, "
                f"etag={resp.etag}, request_id={resp.request_id}"
            )
            return f"https://media.jiqid.com/{key}"

        except Exception as e:
            log.error(f"[OSS Upload Error] key={key}, error={e!r}")
            return ""


oss_client = AliOSSClient(
    access_key_id=settings.OSS_ACCESS_KEY_ID,
    access_key_secret=settings.OSS_ACCESS_KEY_SECRET,
    bucket=settings.OSS_BUCKET,
    region=settings.OSS_REGION,
)


async def main():
    key = "K10/feedback/log/test.log"
    data = "Hello, OSS!".encode("utf-8")

    await oss_client.upload_bytes(key, data)
    await oss_client.close()


if __name__ == "__main__":
    asyncio.run(main())
