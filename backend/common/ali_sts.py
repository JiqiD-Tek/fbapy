import json

from alibabacloud_sts20150401.client import Client
from alibabacloud_sts20150401.models import AssumeRoleRequest
from alibabacloud_tea_openapi.models import Config

from backend.common.log import log
from backend.core.conf import settings


class STSClient:
    def __init__(self, access_key_id, access_key_secret) -> None:
        self.config = Config(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
            endpoint='sts.cn-hangzhou.aliyuncs.com',
            connect_timeout=5000,
            read_timeout=10000,
        )
        self.client = Client(self.config)

        self.role_arn = 'acs:ram::1685160280862218:role/k11'
        self.role_session_name = 'alice'

    def assume_role(self, duration=3600, policy=None):
        """
        获取临时凭证
        """
        request = AssumeRoleRequest(
            role_arn=self.role_arn, role_session_name=self.role_session_name, duration_seconds=duration
        )

        if policy:
            request.policy = json.dumps(policy)

        response = self.client.assume_role(request)

        creds = response.body.credentials
        return {
            'access_key_id': creds.access_key_id,
            'access_key_secret': creds.access_key_secret,
            'security_token': creds.security_token,
            'expiration': creds.expiration,
        }


sts_client = STSClient(
    access_key_id=settings.OSS_ACCESS_KEY_ID,
    access_key_secret=settings.OSS_ACCESS_KEY_SECRET,
)


def main() -> None:
    credentials = sts_client.assume_role()

    if credentials:
        log.info(f'AccessKeyId: {credentials["access_key_id"]}')
        log.info(f'AccessKeySecret: {credentials["access_key_secret"]}')
        log.info(f'SecurityToken: {credentials["security_token"]}')
        log.info(f'Expiration: {credentials["expiration"]}')


# 使用示例
if __name__ == '__main__':
    main()
