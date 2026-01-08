# -*- coding: UTF-8 -*-
"""
Aliyun SMS Async Service (CN + Global)
Author: guhua@jiqid.com
"""
import asyncio
import json
from typing import Literal

from alibabacloud_credentials.client import Client as CredentialClient
from alibabacloud_credentials.models import Config as CredentialConfig
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_tea_util import models as util_models

# CN
from alibabacloud_dysmsapi20170525.client import Client as SmsCnClient
from alibabacloud_dysmsapi20170525 import models as sms_cn_models

# Global
from alibabacloud_dysmsapi20180501.client import Client as SmsGlobalClient
from alibabacloud_dysmsapi20180501 import models as sms_global_models

from backend.common.log import log
from backend.core.conf import settings


class AliSmsClient:
    def __init__(
            self,
            access_key_id: str,
            access_key_secret: str,
            sign_name: str,
            template_code: str,
            cn_endpoint: str = "dysmsapi.aliyuncs.com",
            global_endpoint: str = "dysmsapi.eu-central-1.aliyuncs.com",
    ):
        self.sign_name = sign_name
        self.template_code = template_code

        credential = CredentialClient(
            config=CredentialConfig(
                type="access_key",
                access_key_id=access_key_id,
                access_key_secret=access_key_secret,
            )
        )

        # CN client
        self.cn_client = SmsCnClient(
            open_api_models.Config(
                credential=credential,
                endpoint=cn_endpoint,
            )
        )

        # Global client
        self.global_client = SmsGlobalClient(
            open_api_models.Config(
                credential=credential,
                endpoint=global_endpoint,
            )
        )

    # ----------------------------
    # Public API
    # ----------------------------
    async def send_code(self, to: str, code: str) -> bool:
        """
        统一发送验证码入口
        """
        if to.startswith('86'):  # CN
            return await self._send_cn(to, code)
        else:
            return await self._send_global(to, code)

    # ----------------------------
    # CN SMS
    # ----------------------------
    async def _send_cn(self, phone: str, code: str) -> bool:
        payload = json.dumps({"code": code}, ensure_ascii=False)

        req = sms_cn_models.SendSmsRequest(
            sign_name=self.sign_name,
            template_code=self.template_code,
            phone_numbers=phone,
            template_param=payload,
        )

        try:
            resp = await self.cn_client.send_sms_with_options_async(
                req, util_models.RuntimeOptions()
            )
            log.info(
                f"[SMS CN] phone={phone}, code={resp.body.code}, msg={resp.body.message}"
            )
            return resp.body.code == "OK"

        except Exception as e:
            log.error(f"[SMS CN ERROR] phone={phone}, error={e!r}")
            return False

    # ----------------------------
    # Global SMS
    # ----------------------------
    async def _send_global(
            self, to: str, code: str
    ) -> bool:
        message = (
            f"Your verification code is {code}. "
            f"It will expire in 5 minutes. "
            f"Do not share this code with anyone."
        )

        req = sms_global_models.SendMessageToGlobeRequest(
            to=to, message=message,
        )

        try:
            resp = await self.global_client.send_message_to_globe_with_options_async(
                req, util_models.RuntimeOptions()
            )
            log.info(
                f"[SMS GLOBAL] to={to}, code={resp.body.response_code}, "
                f"msg={resp.body.response_description}"
            )
            return resp.body.response_code == "OK"

        except Exception as e:
            log.error(f"[SMS GLOBAL ERROR] to={to}, error={e!r}")
            return False


sms_client = AliSmsClient(
    access_key_id=settings.SMS_ACCESS_KEY_ID,
    access_key_secret=settings.SMS_ACCESS_KEY_SECRET,
    sign_name=settings.SMS_SIGN_NAME,
    template_code=settings.SMS_TEMPLATE_CODE,
)


async def main():
    # 国内
    await sms_client.send_code("8615050522761", "1234")

    # 国际
    await sms_client.send_code("254798789709", "1234")


if __name__ == "__main__":
    asyncio.run(main())
