# -*- coding: UTF-8 -*-
"""
Aliyun SMS Async Service
Author: guhua@jiqid.com
"""

import asyncio

from alibabacloud_dysmsapi20180501.client import Client as Dysmsapi20180501Client
from alibabacloud_credentials.client import Client as CredentialClient
from alibabacloud_credentials.models import Config as CredentialConfig
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_dysmsapi20180501 import models as dysmsapi_20180501_models
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
            endpoint: str = "dysmsapi.eu-central-1.aliyuncs.com",
    ):
        self.sign_name = sign_name
        self.template_code = template_code
        self.endpoint = endpoint

        # ---- Create SMS Client ----
        credential_config = CredentialConfig(
            type="access_key",
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
        )
        credential = CredentialClient(config=credential_config)

        config = open_api_models.Config(
            credential=credential,
            endpoint=endpoint,
        )

        self.client: Dysmsapi20180501Client = Dysmsapi20180501Client(config)

    async def send_global(self, to: str, message: str, from_: str) -> bool:
        """
        国际短信 方法
        """
        req = dysmsapi_20180501_models.SendMessageToGlobeRequest(
            to=to,
            from_=from_,
            message=message
        )
        runtime = util_models.RuntimeOptions()
        try:
            resp = await self.client.send_message_to_globe_with_options_async(req, runtime)
            return resp.body.response_code == "OK"
        except Exception as e:
            log.error(f"[SMS ERROR] to={to}, error={e!r}")
            return False


sms_client = AliSmsClient(
    access_key_id=settings.SMS_ACCESS_KEY_ID,
    access_key_secret=settings.SMS_ACCESS_KEY_SECRET,
    template_code=settings.SMS_TEMPLATE_CODE,
    sign_name=settings.SMS_SIGN_NAME,
)


async def main():
    await sms_client.send_global("+861505052761", "Your code is: 666666", "JIQID")


if __name__ == "__main__":
    asyncio.run(main())
