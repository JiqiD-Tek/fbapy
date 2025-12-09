# -*- coding: UTF-8 -*-
"""
Aliyun SMS Async Service
Author: guhua@jiqid.com
"""

import asyncio
import json

from alibabacloud_credentials.client import Client as CredentialClient
from alibabacloud_credentials.models import Config as CredentialConfig
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_dysmsapi20170525.client import Client as SmsClient
from alibabacloud_dysmsapi20170525 import models as sms_models
from alibabacloud_tea_util import models as util_models

from backend.common.log import log
from backend.core.conf import settings


class AliSmsClient:
    def __init__(
            self,
            access_key_id: str,
            access_key_secret: str,
            sign_name: str,
            template_code: str,
            endpoint: str = "dysmsapi.aliyuncs.com",
    ):
        self.sign_name = sign_name
        self.template_code = template_code
        self.endpoint = endpoint

        # ---- Create SMS Client ----
        credential_config = CredentialConfig(
            type="access_key",
            access_key_id=access_key_id,
            access_key_secret=access_key_secret
        )
        credential = CredentialClient(config=credential_config)

        config = open_api_models.Config(
            credential=credential,
            endpoint=endpoint
        )

        # Reusable client
        self.client: SmsClient = SmsClient(config)

    async def send_code(self, phone: str, code: str) -> bool:
        """
        发送验证码（推荐使用此方法）
        """
        payload = json.dumps({"code": code}, ensure_ascii=False)
        return await self._send_sms(phone, payload)

    async def _send_sms(self, phone: str, template_param_json: str) -> bool:
        """
        底层发送 SMS 方法
        """
        req = sms_models.SendSmsRequest(
            sign_name=self.sign_name,
            template_code=self.template_code,
            phone_numbers=phone,
            template_param=template_param_json
        )

        try:
            runtime = util_models.RuntimeOptions()
            resp = await self.client.send_sms_with_options_async(req, runtime)

            log.info(f"[SMS] Sent to {phone}, status={resp.body.code}, message={resp.body.message}")

            return resp.body.code == "OK"

        except Exception as e:
            log.error(f"[SMS ERROR] phone={phone}, error={e!r}")
            return False


sms_client = AliSmsClient(
    access_key_id=settings.SMS_ACCESS_KEY_ID,
    access_key_secret=settings.SMS_ACCESS_KEY_SECRET,
    sign_name=settings.SMS_SIGN_NAME,
    template_code=settings.SMS_TEMPLATE_CODE,
)


async def main():
    await sms_client.send_code("15050522761", "666666")


if __name__ == "__main__":
    asyncio.run(main())
