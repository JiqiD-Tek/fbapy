from pydantic import Field

from backend.common.schema import SchemaBase


class SmsSendDetail(SchemaBase):
    """短信发送结果"""

    success: bool = Field(description='短信是否发送成功')
    status: str = Field(description='阿里云返回状态')
    message: str = Field(description='阿里云返回信息')


class GetCaptchaDetail(SchemaBase):
    """验证码详情"""

    is_enabled: bool = Field(description='是否启用')
    expire_seconds: int = Field(description='过期秒数')
    uuid: str = Field(description='唯一标识')
    sms: SmsSendDetail | None = Field(default=None, description='短信发送结果')
