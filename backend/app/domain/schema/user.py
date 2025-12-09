# -*- coding: UTF-8 -*-
"""
@Project : fbapy
@File    : user.py
@Author  : guhua@jiqid.com
@Date    : 2025/11/25 14:47
"""
from datetime import datetime
from typing import Optional

from pydantic import ConfigDict, Field, EmailStr

from backend.common.schema import SchemaBase


class DeviceAuthSchemaBase(SchemaBase):
    """设备认证基础模型"""

    did: str = Field(description='设备 ID')
    sn: str = Field(description='设备序列号')
    mac: str = Field(description='MAC 地址')
    model: str = Field(description='设备型号')
    timestamp: int = Field(description='时间戳')
    nonce: str = Field(description='防重放')
    signature: str = Field(description='签名')


class AuthSchemaBase(SchemaBase):
    """用户认证基础模型"""

    phone: str = Field(description='手机号')
    device: DeviceAuthSchemaBase = Field(description='设备认证信息')


class AuthLoginParam(AuthSchemaBase):
    """用户登录参数"""

    uuid: str | None = Field(None, description='验证码 UUID')
    captcha: str | None = Field(None, description='验证码')


class UserSchemaBase(SchemaBase):
    """用户基础模型"""

    phone: str = Field(description='手机号')
    username: Optional[str] = Field(None, description='用户名')
    nickname: Optional[str] = Field(None, description='昵称')
    email: Optional[EmailStr] = Field(None, description='邮箱')
    avatar: Optional[str] = Field(None, description='头像')
    sex: Optional[int] = Field(None, description='性别(1男 2女)')
    birthday: Optional[datetime] = Field(None, description='生日')


class CreateUserParam(UserSchemaBase):
    """创建用户参数"""

    class Config:
        # 明确配置
        validate_default = True
        arbitrary_types_allowed = True

        # 重写 __init__ 确保所有可选字段都被处理

    def __init__(self, **data):
        # 为所有可选字段提供默认值
        optional_fields = ['username', 'nickname', 'email', 'avatar', 'sex', 'birthday']

        for field in optional_fields:
            if field not in data:
                data[field] = None

        super().__init__(**data)


class UserLoginByPhoneParam(SchemaBase):
    """手机号登录参数"""

    phone: str = Field(description='手机号')
    code: str = Field(description='验证码')


class UserLoginByPasswordParam(SchemaBase):
    """密码登录参数（备用）"""

    phone: str = Field(description='手机号')
    password: str = Field(description='密码')


class SendVerificationCodeParam(SchemaBase):
    """发送验证码参数"""

    phone: str = Field(description='手机号')
    type: str = Field(description='验证码类型(register/login/reset)')


class VerifyCodeParam(SchemaBase):
    """验证验证码参数"""

    phone: str = Field(description='手机号')
    code: str = Field(description='验证码')
    type: str = Field(description='验证码类型(register/login/reset)')


class UpdateUserParam(SchemaBase):
    """更新用户参数"""

    phone: Optional[str] = Field(None, description='手机号')


class SetPasswordParam(SchemaBase):
    """设置密码参数（注册后补充或修改）"""

    password: str = Field(description='密码')
    confirm_password: str = Field(description='确认密码')


class ResetPasswordByPhoneParam(SchemaBase):
    """通过手机号重置密码"""

    phone: str = Field(description='手机号')
    code: str = Field(description='验证码')
    new_password: str = Field(description='新密码')
    confirm_password: str = Field(description='确认密码')


class BindPhoneParam(SchemaBase):
    """绑定手机号参数"""

    phone: str = Field(description='手机号')
    code: str = Field(description='验证码')


class DeleteUserParam(SchemaBase):
    """删除用户参数"""

    pks: list[int] = Field(description='用户 ID 列表')


class GetUserInfoDetail(UserSchemaBase):
    """用户详情"""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int = Field(description='用户 ID')
    uuid: str = Field(description='用户UUID')
    last_login_time: Optional[datetime] = Field(None, description='上次登录时间')
