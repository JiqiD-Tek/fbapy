import shutil

from functools import cache
from re import Pattern
from typing import Any, Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from backend.core.path_conf import ENV_EXAMPLE_FILE_PATH, ENV_FILE_PATH
from backend.plugin.settings_source import PluginSettingsSource


class Settings(BaseSettings):
    """全局配置"""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH,
        env_file_encoding='utf-8',
        extra='allow',
        case_sensitive=True,
    )

    @classmethod
    def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """自定义配置源优先级"""
        return env_settings, dotenv_settings, PluginSettingsSource(settings_cls)

    # .env 当前环境
    ENVIRONMENT: Literal['dev', 'prod']

    # FastAPI
    FASTAPI_API_V1_PATH: str = '/api/v1'
    FASTAPI_TITLE: str = 'fba'
    FASTAPI_DESCRIPTION: str = 'FastAPI Best Architecture'
    FASTAPI_DOCS_URL: str = '/docs'
    FASTAPI_REDOC_URL: str = '/redoc'
    FASTAPI_OPENAPI_URL: str | None = '/openapi'
    FASTAPI_STATIC_FILES: bool = True

    # .env 数据库
    DATABASE_TYPE: Literal['mysql', 'postgresql']
    DATABASE_HOST: str
    DATABASE_PORT: int
    DATABASE_USER: str
    DATABASE_PASSWORD: str

    # 数据库
    DATABASE_ECHO: bool | Literal['debug'] = False
    DATABASE_POOL_ECHO: bool | Literal['debug'] = False
    DATABASE_SCHEMA: str = 'fba'
    DATABASE_CHARSET: str = 'utf8mb4'
    DATABASE_PK_MODE: Literal['autoincrement', 'snowflake'] = 'autoincrement'

    # .env Redis
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_PASSWORD: str
    REDIS_DATABASE: int

    # Redis
    REDIS_TIMEOUT: int = 5

    # TSDB
    TSDB_ENABLED: bool = False
    TSDB_SCHEME: Literal['http', 'https'] = 'http'
    TSDB_HOST: str = '127.0.0.1'
    TSDB_PORT: int = 6041
    TSDB_USER: str = 'root'
    TSDB_PASSWORD: str = ''
    TSDB_DATABASE: str = 'fba'
    TSDB_REQUEST_TIMEOUT_SECONDS: float = 10.0
    TSDB_KEEP_DAYS: int = 30

    # 缓存
    CACHE_LOCAL_ENABLED: bool = True
    CACHE_LOCAL_MAXSIZE: int = 100000
    CACHE_LOCAL_TTL: int = 60 * 60 * 2  # 2 小时
    CACHE_REDIS_TTL: int = 60 * 60 * 2  # 2 小时
    CACHE_CONFIG_REDIS_PREFIX: str = 'fba:cache:config'
    CACHE_DICT_REDIS_PREFIX: str = 'fba:cache:dict'
    CACHE_PUBSUB_CHANNEL: str = 'fba:cache:invalidate'
    CACHE_PUBSUB_RECONNECT_DELAY: int = 5  # 重连延迟（秒）
    CACHE_PUBSUB_MAX_RECONNECT_ATTEMPTS: int = 10  # 最大重连次数

    # .env Snowflake
    SNOWFLAKE_DATACENTER_ID: int | None = None
    SNOWFLAKE_WORKER_ID: int | None = None

    # Snowflake
    SNOWFLAKE_REDIS_PREFIX: str = 'fba:snowflake'
    SNOWFLAKE_HEARTBEAT_INTERVAL_SECONDS: int = 30
    SNOWFLAKE_NODE_TTL_SECONDS: int = 60

    # .env Token
    TOKEN_SECRET_KEY: str  # 密钥 secrets.token_urlsafe(32)

    # Token
    TOKEN_ALGORITHM: str = 'HS256'
    TOKEN_EXPIRE_SECONDS: int = 60 * 60 * 24  # 1 天
    TOKEN_REFRESH_EXPIRE_SECONDS: int = 60 * 60 * 24 * 7  # 7 天
    TOKEN_REDIS_PREFIX: str = 'fba:token'
    TOKEN_EXTRA_INFO_REDIS_PREFIX: str = 'fba:token_extra_info'
    TOKEN_ONLINE_REDIS_PREFIX: str = 'fba:token_online'
    TOKEN_REFRESH_REDIS_PREFIX: str = 'fba:refresh_token'
    TOKEN_REQUEST_PATH_EXCLUDE: list[str] = [  # JWT / RBAC 路由白名单
        f'{FASTAPI_API_V1_PATH}/auth/login',
        f'{FASTAPI_API_V1_PATH}/live/coze/v1/chat',  # 聊天
    ]
    TOKEN_REQUEST_PATH_EXCLUDE_PATTERN: list[Pattern[str]] = []  # JWT / RBAC 路由白名单（正则）

    # 用户安全
    USER_LOCK_REDIS_PREFIX: str = 'fba:user:lock'
    USER_LOCK_THRESHOLD: int = 5  # 用户密码错误锁定阈值，0 表示禁用锁定
    USER_LOCK_SECONDS: int = 60 * 5  # 5 分钟
    USER_PASSWORD_EXPIRY_DAYS: int = 365  # 用户密码有效期，0 表示永不过期
    USER_PASSWORD_REMINDER_DAYS: int = 7  # 用户密码到期提醒，0 表示不提醒
    USER_PASSWORD_HISTORY_CHECK_COUNT: int = 3
    USER_PASSWORD_MIN_LENGTH: int = 6
    USER_PASSWORD_MAX_LENGTH: int = 32
    USER_PASSWORD_REQUIRE_SPECIAL_CHAR: bool = False

    # 登录
    LOGIN_CAPTCHA_ENABLED: bool = True
    LOGIN_CAPTCHA_REDIS_PREFIX: str = 'fba:login:captcha'
    LOGIN_CAPTCHA_EXPIRE_SECONDS: int = 60 * 5  # 5 分钟
    LOGIN_FAILURE_PREFIX: str = 'fba:login:failure'

    # JWT
    JWT_USER_REDIS_PREFIX: str = 'fba:user'

    # RBAC
    RBAC_ROLE_MENU_MODE: bool = True
    RBAC_ROLE_MENU_EXCLUDE: list[str] = []

    # Cookie
    COOKIE_REFRESH_TOKEN_KEY: str = 'fba_refresh_token'
    COOKIE_REFRESH_TOKEN_EXPIRE_SECONDS: int = 60 * 60 * 24 * 7  # 7 天

    # 数据权限
    DATA_PERMISSION_MODEL_EXCLUDE: list[str] = [  # 排除允许进行数据过滤的 SQLA 模型
        'DataScope',
        'DataRule',
        'sys_role_data_scope',
        'sys_data_scope_rule',
    ]
    DATA_PERMISSION_COLUMN_EXCLUDE: list[str] = [  # 排除允许进行数据过滤的 SQLA 模型列
        'id',
        'sort',
        'del_flag',
        'created_time',
        'updated_time',
    ]
    DATA_PERMISSION_MODEL_TEMPLATE_VARIABLES: list[dict[str, str]] = [  # 数据规则模型可用模板变量
        {'key': '__ALL__', 'comment': '所有模型'},
    ]
    DATA_PERMISSION_COLUMN_TEMPLATE_VARIABLES: list[dict[str, str]] = [  # 数据规则字段可用模板变量
        {'key': '__dept_id__', 'comment': '部门 ID'},
        {'key': '__created_by__', 'comment': '创建者'},
    ]
    DATA_PERMISSION_TEMPLATE_VARIABLES: list[dict[str, str]] = [  # 数据规则值可用模板变量
        {'key': '${user_id}', 'comment': '当前登录用户 ID'},
        {'key': '${dept_id}', 'comment': '当前登录用户部门 ID'},
        {'key': '${now}', 'comment': '当前时间'},
    ]

    # Socket.IO
    WS_NO_AUTH_MARKER: str = 'internal'

    # CORS
    CORS_ALLOWED_ORIGINS: list[str] = [  # 末尾不带斜杠
        'http://127.0.0.1',
        'http://localhost:5173',
    ]
    CORS_EXPOSE_HEADERS: list[str] = [
        'X-Request-ID',
    ]

    # 中间件配置
    MIDDLEWARE_CORS: bool = True

    # 请求限制配置
    REQUEST_LIMITER_REDIS_PREFIX: str = 'fba:limiter'

    # 时间配置
    DATETIME_TIMEZONE: str = 'Asia/Shanghai'  # 如：Asia/Shanghai、UTC
    DATETIME_FORMAT: str = '%Y-%m-%dT%H:%M:%S.%f%:z'

    # 文件上传
    UPLOAD_READ_SIZE: int = 1024
    UPLOAD_IMAGE_EXT_INCLUDE: list[str] = ['jpg', 'jpeg', 'png', 'gif', 'webp']
    UPLOAD_IMAGE_SIZE_MAX: int = 5 * 1024 * 1024  # 5 MB
    UPLOAD_VIDEO_EXT_INCLUDE: list[str] = ['mp4', 'mov', 'avi', 'flv']
    UPLOAD_VIDEO_SIZE_MAX: int = 20 * 1024 * 1024  # 20 MB

    # 演示模式配置
    DEMO_MODE: bool = False
    DEMO_MODE_EXCLUDE: set[tuple[str, str]] = {
        ('POST', f'{FASTAPI_API_V1_PATH}/auth/login'),
        ('POST', f'{FASTAPI_API_V1_PATH}/auth/logout'),
        ('GET', f'{FASTAPI_API_V1_PATH}/auth/captcha'),
        ('POST', f'{FASTAPI_API_V1_PATH}/auth/refresh'),
    }

    # IP 定位配置
    IP_LOCATION_PARSE: Literal['online', 'offline', 'false'] = 'offline'
    IP_LOCATION_REDIS_PREFIX: str = 'fba:ip:location'
    IP_LOCATION_EXPIRE_SECONDS: int = 60 * 60 * 24  # 1 天

    # Weather
    WEATHER_API_HOST: str = 'mj7p3y7naa.re.qweatherapi.com'
    WEATHER_API_KEY: str = ''
    WEATHER_DEFAULT_LOCATION: str = '广州'
    WEATHER_TIMEOUT_SECONDS: float = 10.0

    # Trace ID
    TRACE_ID_REQUEST_HEADER_KEY: str = 'X-Request-ID'
    TRACE_ID_LOG_LENGTH: int = 32  # UUID 长度，必须小于等于 32
    TRACE_ID_LOG_DEFAULT_VALUE: str = '-'

    # 日志
    LOG_FORMAT: str = (
        '<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | '
        '<lvl>{level: <8}</> | <cyan>{request_id}</> | '
        '<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - '
        '<level>{message}</level>'
    )

    # 日志（控制台）
    LOG_STD_LEVEL: str = 'DEBUG'

    # 日志（文件）
    LOG_FILE_ACCESS_LEVEL: str = 'INFO'
    LOG_FILE_ERROR_LEVEL: str = 'ERROR'
    LOG_ACCESS_FILENAME: str = 'fba_access.log'
    LOG_ERROR_FILENAME: str = 'fba_error.log'

    # 操作日志
    OPERA_LOG_PATH_EXCLUDE: list[str] = [
        '/favicon.ico',
        '/docs',
        '/redoc',
        '/openapi',
        f'{FASTAPI_API_V1_PATH}/auth/login/swagger',
        f'{FASTAPI_API_V1_PATH}/oauth2/github/callback',
        f'{FASTAPI_API_V1_PATH}/oauth2/google/callback',
    ]
    OPERA_LOG_REDACT_KEYS: list[str] = [
        'password',
        'old_password',
        'new_password',
        'confirm_password',
    ]
    OPERA_LOG_QUEUE_MAXSIZE: int = 100000
    OPERA_LOG_QUEUE_BATCH_CONSUME_SIZE: int = 100
    OPERA_LOG_QUEUE_TIMEOUT: int = 60  # 1 分钟

    # Plugin 配置
    PLUGIN_REQUIRED: list[str] = ['dict']
    PLUGIN_PIP_CHINA: bool = True
    PLUGIN_PIP_INDEX_URL: str = 'https://mirrors.aliyun.com/pypi/simple/'
    PLUGIN_PIP_MAX_RETRY: int = 3
    PLUGIN_REDIS_PREFIX: str = 'fba:plugin'

    # I18n 配置
    I18N_DEFAULT_LANGUAGE: str = 'zh-CN'

    # Grafana
    GRAFANA_METRICS_ENABLE: bool = False
    GRAFANA_OTLP_GRPC_ENDPOINT: str = 'fba_alloy:4317'

    ##################################################
    # [ App ] task
    ##################################################
    # .env Redis
    CELERY_BROKER_REDIS_DATABASE: int

    # .env RabbitMQ
    # docker run -d --hostname fba-mq --name fba-mq  -p 5672:5672 -p 15672:15672 rabbitmq:latest
    CELERY_RABBITMQ_HOST: str
    CELERY_RABBITMQ_PORT: int
    CELERY_RABBITMQ_USERNAME: str
    CELERY_RABBITMQ_PASSWORD: str

    # 基础配置
    CELERY_BROKER: Literal['rabbitmq', 'redis'] = 'redis'
    CELERY_RABBITMQ_VHOST: str = ''
    CELERY_REDIS_PREFIX: str = 'fba:celery'
    CELERY_TASK_MAX_RETRIES: int = 5

    ##################################################
    # [ Plugin ] code_generator
    ##################################################
    CODE_GENERATOR_DOWNLOAD_ZIP_FILENAME: str

    ##################################################
    # [ Plugin ] oauth2
    ##################################################
    # .env
    OAUTH2_GITHUB_CLIENT_ID: str
    OAUTH2_GITHUB_CLIENT_SECRET: str
    OAUTH2_GOOGLE_CLIENT_ID: str
    OAUTH2_GOOGLE_CLIENT_SECRET: str

    # 基础配置（in plugin.toml）
    OAUTH2_STATE_REDIS_PREFIX: str
    OAUTH2_STATE_EXPIRE_SECONDS: int
    OAUTH2_GITHUB_REDIRECT_URI: str
    OAUTH2_GOOGLE_REDIRECT_URI: str
    OAUTH2_FRONTEND_LOGIN_REDIRECT_URI: str
    OAUTH2_FRONTEND_BINDING_REDIRECT_URI: str

    ##################################################
    # [ Plugin ] email
    ##################################################
    # .env
    EMAIL_USERNAME: str
    EMAIL_PASSWORD: str

    # 基础配置（in plugin.toml）
    EMAIL_HOST: str
    EMAIL_PORT: int
    EMAIL_SSL: bool
    EMAIL_CAPTCHA_REDIS_PREFIX: str
    EMAIL_CAPTCHA_EXPIRE_SECONDS: int

    # 脱敏密钥
    ENCRYPT_SECRET_KEY: str = ''  # AES-256

    # 三元组
    MASTER_SECRET: str = ''  # 主密钥
    KEY_SALT: str = ''  # 密钥盐
    AUTH_SECRET_MIN_LENGTH: int = 16

    # SMS
    SMS_ACCESS_KEY_ID: str = ''
    SMS_ACCESS_KEY_SECRET: str = ''
    SMS_SIGN_NAME: str = ''
    SMS_TEMPLATE_CODE: str = ''

    # OSS
    OSS_ACCESS_KEY_ID: str = ''
    OSS_ACCESS_KEY_SECRET: str = ''
    OSS_BUCKET: str = ''
    OSS_REGION: str = ''

    # WeChat Mini Program
    MINI_APPID: str = ''
    MINI_SECRET: SecretStr = ''
    MINI_HOST: str = 'https://api.weixin.qq.com'
    MINI_REQUEST_TIMEOUT_SECONDS: float = 10.0
    MINI_ACCESS_TOKEN_REDIS_PREFIX: str = 'fba:mini:access_token'
    MINI_ACCESS_TOKEN_EXPIRE_BUFFER_SECONDS: int = 300
    MINI_PROVISION_TOKEN_REDIS_PREFIX: str = 'fba:mini:provision'
    MINI_PROVISION_TOKEN_EXPIRE_SECONDS: int = 300

    # Ximalaya
    XIMALAYA_APP_KEY: str = ''
    XIMALAYA_APP_SECRET: SecretStr = ''
    XIMALAYA_SN: str = ''

    # livekit
    LIVEKIT_URL: str = ''
    LIVEKIT_API_KEY: str = ''
    LIVEKIT_API_SECRET: str = ''

    # Coze
    COZE_CLIENT_ID: str = ''
    COZE_PRIVATE_KEY: str = ''
    COZE_PUBLIC_KEY_ID: str = ''
    COZE_BOT_ID: str = ''

    # MQTT
    MQTT_HOST: str = '10.240.225.23'
    MQTT_PORT: int = 1883
    MQTT_USERNAME: str = 'admin'
    MQTT_JWT_SECRET: str = ''
    MQTT_PASSWORD: str = ''
    MQTT_UP_TOPICS: list[str] = [
        '$share/group/k11/+/up/status',
        '$share/group/k11/+/up/property',
        '$share/group/k11/+/up/ack',
        '$share/group/js61/+/up/status',
        '$share/group/js61/+/up/property',
        '$share/group/js61/+/up/ack',
    ]

    # 微软 大模型
    AZURE_OPENAI_MODEL: str = ''
    AZURE_OPENAI_ENDPOINT: str = ''
    AZURE_OPENAI_SUBSCRIPTION_KEY: SecretStr = ''
    AZURE_OPENAI_API_VERSION: str = ''

    # 火山 TTS
    JS61_BYTES_TTS_APPID: str = ''
    JS61_BYTES_TTS_TOKEN: str = ''

    BYTES_TTS_APPID: str = ''
    BYTES_TTS_TOKEN: str = ''
    BYTES_TTS_STREAM_WS_URL: str = 'wss://openspeech.bytedance.com/api/v3/tts/bidirection'
    BYTES_TTS_STREAM_RESOURCE_ID: str = 'seed-tts-2.0'
    BYTES_TTS_STREAM_AUDIO_FORMAT: str = 'mp3'
    BYTES_TTS_STREAM_SPEECH_RATE: int = 0
    BYTES_TTS_STREAM_LOUDNESS_RATE: int = 0
    BYTES_TTS_LONG_RESOURCE_ID: str = 'seed-icl-2.0'
    BYTES_TTS_LONG_QUERY_RESOURCE_ID: str = ''
    BYTES_TTS_LONG_SUBMIT_URL: str = 'https://openspeech.bytedance.com/api/v3/tts/submit'
    BYTES_TTS_LONG_QUERY_URL: str = 'https://openspeech.bytedance.com/api/v3/tts/query'
    BYTES_TTS_LONG_TIMEOUT_SECONDS: float = 60.0
    BYTES_TTS_LONG_QUERY_INTERVAL_SECONDS: float = 2.0
    BYTES_TTS_LONG_QUERY_TIMEOUT_SECONDS: float = 900.0

    # 火山 OpenAPI
    BYTES_OPENAPI_ACCESS_KEY: str = ''
    BYTES_OPENAPI_SECRET_KEY: SecretStr = ''
    JS61_BYTES_OPENAPI_ACCESS_KEY: str = ''
    JS61_BYTES_OPENAPI_SECRET_KEY: SecretStr = ''
    BYTES_OPENAPI_HOST: str = ''
    BYTES_OPENAPI_REGION: str = 'cn-north-1'
    BYTES_OPENAPI_SERVICE: str = 'speech_saas_prod'
    BYTES_OPENAPI_VERSION: str = '2025-05-21'
    BYTES_OPENAPI_TIMEOUT_SECONDS: float = 10.0

    # 豆包大模型
    DOUBAO_API_KEY: SecretStr = ''
    DOUBAO_BASE_URL: str = ''

    # Viking Memory
    VIKING_MEMORY_ENABLED: bool = False
    VIKING_MEMORY_COLLECTION_NAME: str = ''
    VIKING_MEMORY_PROJECT_NAME: str = 'default'
    VIKING_MEMORY_HOST: str = 'api-knowledgebase.mlp.cn-beijing.volces.com'
    VIKING_MEMORY_REGION: str = 'cn-beijing'
    VIKING_MEMORY_SCHEME: Literal['http', 'https'] = 'https'
    VIKING_MEMORY_TIMEOUT_SECONDS: int = 30
    VIKING_MEMORY_API_KEY: SecretStr = ''
    VIKING_MEMORY_EVENT_MEMORY_TYPES: list[str] = ['event_v1']
    VIKING_MEMORY_PROFILE_MEMORY_TYPES: list[str] = ['profile_v1']

    @model_validator(mode='before')
    @classmethod
    def check_env(cls, values: Any) -> Any:
        """检查环境变量"""
        if values.get('ENVIRONMENT') == 'prod':
            # FastAPI
            # values['FASTAPI_OPENAPI_URL'] = None
            # values['FASTAPI_STATIC_FILES'] = False

            # task
            values['CELERY_BROKER'] = 'rabbitmq'

            # Grafana
            values['GRAFANA_METRICS_ENABLE'] = True

        return values


@cache
def get_settings() -> Settings:
    """获取全局配置单例"""
    if not ENV_FILE_PATH.exists():
        shutil.copy(ENV_EXAMPLE_FILE_PATH, ENV_FILE_PATH)
    return Settings()


# 创建全局配置实例
settings = get_settings()
