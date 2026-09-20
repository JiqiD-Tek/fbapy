# MQTT 设备请求-响应测试说明

本目录用于验证项目的 MQTT 设备通信，覆盖 MQTT 5 标准 Request-Response、MQTT 3.1.1 兼容请求-响应、异步命令发布、设备幂等和
MQTTClient 稳定性测试。

这里的模拟程序连接测试环境中的 MQTT Broker，代码仅用于联调和稳定性验证。生产环境不要直接使用测试文件中的 Broker 地址、账号和密钥。

## 1. 目录结构

```text
backend/common/mqtt/
├── types.py       # 配置、消息上下文、发布结果和订阅类型
├── client.py      # MQTTClient：连接、重连、发布、订阅和请求-响应
├── dependency.py  # MQTTClient 单例、应用配置和生命周期管理
└── __init__.py    # 对外统一导出

backend/tests/mqtt/
├── v5/
│   ├── device_service_v5.py   # MQTT 5 设备端模拟
│   └── server_service_v5.py   # MQTT 5 服务端请求模拟
├── v311/
│   ├── device_service_v311.py # MQTT 3.1.1 设备端模拟
│   └── server_service_v311.py # MQTT 3.1.1 服务端请求模拟
├── test_mqtt_stability.py      # 不连接真实 Broker 的稳定性测试
└── README.md
```

业务代码统一从下面的入口导入：

```python
from backend.common.mqtt import MQTTClient, MQTTConfig, MQTTConnectionError, MQTTVersion
```

## 2. MQTT 基本概念

MQTT 是通过 Broker 转发消息的发布/订阅协议：

```text
Publisher  ->  MQTT Broker  ->  Subscriber
```

| 概念               | 说明                                          |
|------------------|---------------------------------------------|
| Broker           | MQTT 消息服务器，负责接收、路由和转发消息                     |
| Client           | 连接 Broker 的客户端，例如服务端或设备                     |
| Topic            | 消息地址，例如 `js61/TEST_DEVICE_DID/down/request` |
| Publish          | 向 Topic 发布消息                                |
| Subscribe        | 订阅 Topic，接收匹配的消息                            |
| Payload          | 消息正文，可以是 JSON、字符串或二进制                       |
| QoS              | 消息服务质量：0、1、2                                |
| Client ID        | MQTT 连接的唯一标识，同一 Broker 上不能被多个连接同时复用         |
| MID              | Paho 对 MQTT 报文分配的内部编号，不是业务 `msg_id`         |
| Correlation Data | MQTT 5 请求和响应之间的关联数据                         |

MQTT 的 `publish()` 默认是异步消息发送。消息发布成功不代表设备已经执行完命令；需要设备响应时，应使用 `request()`。

## 3. `backend/common/mqtt/client.py` 模块说明

### 3.1 模块职责

`MQTTClient` 是项目对 Paho MQTT 客户端的异步封装，负责 MQTT 传输层能力：

- 创建和管理 Paho MQTT 连接；
- 使用 MQTT 5 Callback API v2 接收连接、发布、订阅和消息回调；
- 使用 Paho 原生退避重连，并在重连成功后恢复已注册 Topic；
- 将 Paho 线程中的回调安全地切回 asyncio 事件循环；
- 提供发布、订阅、取消订阅和 MQTT 5 请求-响应 API；
- 管理发布确认、请求响应、超时和断线时的 Future 清理。

它不负责设备权限、设备归属、业务 action 实现、数据库持久化或 HTTP 响应。设备路由和业务协议由上层的 `DeviceGateway`、
`DeviceMQTTConsumer` 等模块负责。

### 3.2 配置和创建

`MQTTClient` 通过 `MQTTConfig` 接收连接参数：

```python
from backend.common.mqtt import MQTTClient, MQTTConfig, MQTTVersion

client = MQTTClient(MQTTConfig(
    host='mqtt.example.com',
    port=1883,
    username='admin',
    password='jwt-password',
    version=MQTTVersion.V5,
    client_id='server-instance-a',
    subscribe_timeout=5,
    publish_timeout=5,
    shutdown_timeout=5,
    callback_queue_maxsize=10000,
    request_max_pending=200,
    max_inflight_messages=100,
    max_queued_messages=1000,
))
```

生产代码通常通过 `MQTTDependency.get_manager()` 获取应用级单例，不要在每个 API 请求中创建新的 MQTT 连接：

```python
from backend.common.mqtt import MQTTDependency

mqtt_client = await MQTTDependency.get_manager()
```

### 3.3 生命周期 API

```python
await client.connect()
await client.disconnect()
```

Web 应用通过 `MQTTDependency` 统一管理共享客户端的连接和断开。命令行脚本或独立测试直接创建客户端时，应使用
`try/finally` 确保异常时也能清理连接和回调任务：

```python
client = MQTTClient(config)
try:
    if not await client.connect():
        raise MQTTConnectionError('MQTT 连接失败')
    result = await client.publish(
        'js61/TEST_DEVICE_DID/down/command',
        {'msg_id': 'command-001'},
    )
finally:
    await client.disconnect()
```

`connect()` 会启动单个回调处理协程和 Paho 网络循环；连接成功后，客户端会订阅自己的响应 Topic。意外断线后的退避重连由 Paho
负责，重连成功后重新订阅业务 Topic。`disconnect()` 会停止 Paho 网络线程、结束 pending Future 并清空回调队列。

### 3.4 公共消息 API

| 方法                                                             | 用途                     | 返回值                  |
|----------------------------------------------------------------|------------------------|----------------------|
| `subscribe(topic, callback, qos)`                              | 注册 Topic 和异步回调         | `None`               |
| `unsubscribe(topic)`                                           | 删除 Topic、回调和 Broker 订阅 | `bool`               |
| `publish(topic, payload, *, qos, retain, timeout, properties)` | 发布消息并等待 Paho 发布确认      | `MQTTPublishResult`  |
| `request(topic, payload, *, qos, timeout)`                     | MQTT 5 发布请求并等待设备响应     | `MQTTMessageContext` |

订阅示例：

```python
async def on_device_event(message: MQTTMessageContext) -> None:
    print(message.topic, message.payload)


await client.subscribe(
    'js61/+/up/event',
    on_device_event,
    qos=1,
)
```

普通订阅消息统一进入一个有界异步队列，并固定由一个回调处理协程消费，保证单个客户端内消息按队列顺序处理。`subscribe()` 会等待
Broker 返回 SUBACK；本地发送订阅成功但 Broker 拒绝订阅时，调用方会立即收到异常。

### 3.5 `publish()` 的确认语义

`publish()` 内部使用 Paho 返回的 PUBLISH MID 保存一个发布确认 Future：

```text
Paho publish() -> MID
Broker PUBACK  -> on_publish(MID)
               -> 完成 ack Future
               -> 返回 MQTTPublishResult
```

因此：

- 正常返回 `MQTTPublishResult` 表示消息完成 MQTT 发布确认；
- 未连接、Broker 拒绝和发布超时会分别抛出连接异常或 `TimeoutError`，不再通过错误字符串判断结果；
- 不表示设备已经收到、执行或执行成功；
- 设备业务结果需要使用 `request()` 或设备上行事件另行获取。

### 3.6 回调线程模型

Paho 的网络循环运行在线程中，而业务回调运行在 asyncio 事件循环中，数据流如下：

```text
Paho 网络线程
    -> _on_message / _on_publish / _on_subscribe
    -> call_soon_threadsafe()
    -> asyncio 回调队列
    -> 回调处理协程
    -> 业务异步回调
```

普通订阅消息会进入一个有界回调队列。队列达到上限时会丢弃普通业务回调并记录日志；MQTT
5 响应消息则直接根据 Correlation Data 完成对应的请求 Future。

### 3.7 请求状态和响应状态

客户端内部有三类独立的 Future：

```text
_pending_publishes[mid]              -> 发布确认 Future
_pending_requests[correlation_data]  -> 设备响应 Future
_pending_subscriptions[mid]          -> 业务主题 SUBACK Future
```

发布确认 Future 的结果是 `None`，它只表示 PUBLISH 已确认；设备响应 Future 的结果是 `MQTTMessageContext`，它才是 `request()`
返回给调用方的业务响应上下文。

客户端还使用 `_request_semaphore` 限制同时进行中的请求数量，并用 `_response_subscribed` 确保响应 Topic 收到 SUBACK
后才允许发送请求。

### 3.8 模块边界

建议按以下边界使用 `MQTTClient`：

```text
MQTTClient
    连接、重连、发布、订阅、回调分发、请求响应匹配

DeviceGateway
    设备 Topic 生成、msg_id 生成、请求消息封装、响应解码

API / DependsDeviceAuth
    用户认证、设备归属、参数校验、HTTP 错误转换

设备服务或业务模块
    service/action 的具体执行逻辑
```

不要在 `MQTTClient` 中加入数据库查询、用户权限判断、设备业务白名单或具体 action 分支，否则基础通信模块会和云端业务耦合。

### 3.9 Gateway 中的连接使用方式

应用启动时由生命周期管理器创建并连接共享的 MQTTClient：

```text
应用启动
    -> init_mqtt()
    -> MQTTDependency 创建并连接 MQTTClient
    -> 注册 DeviceMQTTConsumer

HTTP 请求
    -> MQTTDependency.get_manager()
    -> DeviceGateway(mqtt_client=共享实例, model=型号, did=设备标识)
    -> gateway.request() / gateway.publish()

应用关闭
    -> close_mqtt()
    -> 断开 MQTTClient 并清理回调任务
```

因此当前 API 层和 Gateway 的使用方式是正确的：

```python
mqtt_client = await MQTTDependency.get_manager()
gateway = DeviceGateway(mqtt_client=mqtt_client, model=model, did=did)
return await gateway.request(...)
```

`DeviceGateway` 是绑定单台设备的轻量请求转发对象，只保存设备路由信息，不负责连接、断开或清理 MQTTClient。单次 HTTP
请求不能调用共享客户端的 `connect()` 或 `disconnect()`，否则会影响其他正在使用该连接的 Gateway 和 Consumer。

```python
# 不要这样做：会断开整个应用共享的 MQTTClient。
try:
    await gateway.request(...)
finally:
    await mqtt_client.disconnect()
```

`MQTTClient` 不提供上下文管理器，避免把应用共享客户端误当成单次请求资源。只有创建该客户端的应用生命周期或独立脚本才拥有关闭连接的责任。

## 4. Topic 协议

项目的 Topic 格式为：

```text
{model}/{did}/{direction}/{category}
```

| Topic                        | 方向        | 用途            | 是否等待设备响应 |
|------------------------------|-----------|---------------|----------|
| `{model}/{did}/down/command` | 服务端 -> 设备 | 异步命令或通知       | 否        |
| `{model}/{did}/down/request` | 服务端 -> 设备 | 请求设备执行操作并返回结果 | 是        |
| `{model}/{did}/up/event`     | 设备 -> 服务端 | 设备事件          | 否        |
| `{model}/{did}/up/property`  | 设备 -> 服务端 | 设备属性或状态上报     | 否        |

`down` 表示服务端发给设备，`up` 表示设备发给服务端，`did` 是设备唯一编码。

MQTT 5 的响应 Topic 不固定使用设备的 `up/response`，而是由请求属性动态指定，格式通常是：

```text
fbapy/{server_client_id}/response
```

MQTT 3.1.1 没有 MQTT 5 的 `Response Topic` 和 `Correlation Data` 属性，因此测试程序将这两个字段放进 JSON Payload 中。
`up/response` 只作为 3.1.1 设备模拟器没有收到响应 Topic 时的默认回退 Topic。

## 5. 两种消息语义

### 5.1 `down/command`：只发布，不等业务响应

适用于不需要立即拿到设备结果的命令：

```python
result = await mqtt_client.publish(
    topic='js61/TEST_DEVICE_DID/down/command',
    payload={
        'msg_id': 'command-001',
        'service': 'system',
        'payload': {'action': 'reboot'},
    },
    qos=1,
)
```

`publish()` 等待 Paho 的发布确认，并返回 `MQTTPublishResult`，但不等待设备处理结果。

### 5.2 `down/request`：发布并等待设备响应

适用于小程序或服务端需要立即取得设备数据的场景：

```python
context = await mqtt_client.request(
    topic='js61/TEST_DEVICE_DID/down/request',
    payload={
        'msg_id': 'request-001',
        'service': 'system',
        'action': 'get_state',
        'payload': {},
    },
    timeout=10,
)
```

这个方法只支持 MQTT 5 配置，因为它依赖 MQTT 5 的请求-响应属性。MQTT 3.1.1 的测试服务端使用独立实现，不能调用
`MQTTClient.request()`。

## 6. MQTT 5 请求-响应流程

`MQTTClient.request()` 的处理顺序如下：

```text
1. 连接 Broker
2. 订阅当前客户端专用的响应 Topic
3. 等待 Broker 返回 SUBACK，确认订阅已经生效
4. 生成唯一 Correlation Data
5. 保存 correlation_data -> response Future
6. 发布带 Response Topic 和 Correlation Data 的请求
7. 设备读取属性并执行操作
8. 设备向 Response Topic 发布响应，并原样返回 Correlation Data
9. 服务端根据 Correlation Data 找到对应 Future
10. request() 返回 MQTTMessageContext
11. 成功、失败或超时后清理 pending 状态
```

请求消息的 MQTT 5 属性如下：

```text
Topic:            js61/TEST_DEVICE_DID/down/request
Response Topic:   fbapy/{server_client_id}/response
Correlation Data: 一段随机唯一的 bytes
```

设备端必须读取 `Response Topic` 和 `Correlation Data`，执行操作后向 Response Topic 发布响应，并原样返回 Correlation
Data。否则服务端无法找到对应 Future，最终会超时。

## 7. MQTT 3.1.1 兼容流程

MQTT 3.1.1 将关联信息放到 Payload：

```json
{
  "msg_id": "request-001",
  "type": "command",
  "service": "system",
  "response_topic": "fbapy/test-server-v311/response",
  "correlation_data": "correlation-001",
  "payload": {
    "action": "ping"
  }
}
```

设备响应时返回：

```json
{
  "type": "response",
  "success": true,
  "msg_id": "request-001",
  "correlation_data": "correlation-001",
  "payload": {
    "accepted": true
  }
}
```

3.1.1 的 `correlation_data` 必须按每次传输原样回传。设备可以缓存 `msg_id` 对应的业务结果，但不能把首次请求的关联数据错误地复用到下一次响应。

## 8. 请求、响应和幂等字段

| 字段                 | 所属层次               | 用途                                     |
|--------------------|--------------------|----------------------------------------|
| `msg_id`           | 业务层                | 标识一次设备业务操作，设备据此实现幂等                    |
| `Correlation Data` | MQTT 5 传输层         | 将响应匹配到服务端的请求 Future                    |
| `correlation_data` | MQTT 3.1.1 Payload | MQTT 3.1.1 中替代 MQTT 5 Correlation Data |
| Paho `mid`         | MQTT 客户端实现层        | 匹配 PUBLISH、SUBSCRIBE 的确认回调             |

设备端模拟器维护最近的 `msg_id` 响应缓存：

```text
第一次收到 msg_id=abc -> 执行业务动作并缓存响应
再次收到 msg_id=abc   -> 不重复执行，直接返回缓存响应
```

真实设备也应采用相同原则，尤其是 QoS 1 可能导致消息重复投递的场景。

## 9. 为什么响应不会串数据

正常实现下，响应通过三层信息隔离：

1. **设备 Topic 隔离**：`device-001` 和 `device-002` 使用不同的 `down/request` Topic，设备应只订阅自己的精确 Topic。
2. **服务端响应 Topic 隔离**：每个 MQTTClient 使用唯一 Client ID 和专用响应 Topic，设备按请求中的 Response Topic 返回。
3. **Correlation Data 隔离**：同一设备的并发请求使用不同关联数据，响应不依赖到达顺序。

仍然需要注意：

- 每个服务端进程必须使用唯一 Client ID；复用 Client ID 会导致 Broker 踢掉旧连接。
- 设备必须原样返回 Correlation Data。
- pending Future 位于进程内存中，断线或进程退出后不能自动跨实例恢复。
- 如果需要跨进程接管请求状态，应使用共享状态存储或任务队列重新设计。

## 10. 服务端通用设备请求 API

当前服务端实际路由为：

```http
POST /api/v1/terminal/device/request
```

请求体：

```json
{
  "service": "system",
  "action": "get_state",
  "payload": {},
  "timeout": 10
}
```

当前实现中，`did` 和 `model` 不由小程序直接传入，而是由 `DependsDeviceAuth` 校验后从设备鉴权上下文取得。这样可以避免客户端伪造其他设备的
DID。

接口层负责认证、设备归属校验、参数校验和错误转换；`DeviceGateway` 负责生成 `msg_id`、生成 `{model}/{did}/down/request`、调用
`MQTTClient.request()` 和解码设备响应，不实现 `get_state`、`reboot` 等具体业务。

统一结果示例：

```json
{
  "request_id": "request-001",
  "device_id": "TEST_DEVICE_DID",
  "success": true,
  "response": {
    "type": "response",
    "success": true,
    "payload": {
      "temperature": 26
    }
  },
  "topic": "fbapy/test-server/response"
}
```

`DeviceGateway.publish()` 和 `DeviceGateway.request()` 都返回上述统一结构。两者的确认语义不同：

- `publish()` 的 `success=true` 只表示 Broker 已确认消息发布，`response` 固定为 `null`，不表示设备已经执行命令；
- `request()` 的 `success` 来自设备响应，`response` 保存设备返回的数据；
- `request_id` 均为服务端生成的业务消息 ID，可用于日志追踪和设备端幂等处理。

“服务端只做通道”不等于完全不校验。建议服务端至少：

- 不允许小程序直接提交任意 MQTT Topic；
- 根据鉴权上下文生成设备 Topic；
- 限制 `service`、`action`、Payload 大小和最大超时时间；
- 不允许客户端覆盖 Response Topic、Correlation Data 或 MQTT Properties；
- 对高风险动作维护轻量白名单或设备型号能力表；
- 记录 `request_id`、`did`、`service`、`action`、耗时和结果。

如果设备操作可能持续几十秒以上，不要长期占用 HTTP 连接，建议改为：

```text
POST /device/commands       -> 返回 request_id
GET  /device/commands/{id}  -> 查询设备处理结果
```

## 11. 并发、超时和可靠性

`MQTTClient` 当前包含以下保护机制：

| 机制                      | 作用                                 |
|-------------------------|------------------------------------|
| 全局 pending Semaphore    | 限制同时进行中的 `request()` 数量            |
| `max_inflight_messages` | 限制 Paho 同时发送中的消息数量                 |
| `max_queued_messages`   | 限制 Paho 本地排队消息数量                   |
| 单一 request deadline     | Semaphore、订阅等待、发布确认和响应等待共用一个截止时间   |
| `on_publish` + Future   | 不使用线程池阻塞等待发布确认                     |
| SUBACK MID 校验           | 响应 Topic 和普通业务 Topic 都检查 Broker 确认   |
| 断线清理 pending            | 连接断开时结束等待中的发布和请求 Future            |
| 有界回调队列                  | 将 Paho 网络线程与 asyncio 业务回调解耦，限制内存增长 |

边界行为：

- `publish()` 成功只代表 MQTT 发布确认成功，不代表设备业务成功。
- `request()` 超时不一定代表设备没有执行，业务动作必须依赖 `msg_id` 幂等。
- 回调队列达到上限时会丢弃普通业务回调并记录日志，应结合容量、消费速度和监控调优。
- 断线后当前进程中的等待请求会失败；Paho 可能按 QoS 语义重发尚未确认的消息，因此设备仍须按 `msg_id` 幂等。
- 当前没有做相同在途请求合并，也没有设备级并发信号量。

## 12. 启动模拟服务

项目根目录为 `D:\project\jiqid-tek\fbapy` 时，按版本成对启动。

### MQTT 5

```powershell
python -m backend.tests.mqtt.v5.device_service_v5
python -m backend.tests.mqtt.v5.server_service_v5
```

测试 Topic：

```text
js61/TEST_DEVICE_DID/down/request
```

### MQTT 3.1.1

```powershell
python -m backend.tests.mqtt.v311.device_service_v311
python -m backend.tests.mqtt.v311.server_service_v311
```

启动顺序：

```text
1. MQTT Broker
2. 对应版本的 device_service
3. 同版本的 server_service
```

MQTT 5 和 MQTT 3.1.1 模拟程序必须成对使用。3.1.1 服务端不会调用 `MQTTClient.request()`，而是在 Payload 中维护
`response_topic` 和 `correlation_data`。

## 13. 自动化测试和排查

稳定性测试不需要连接真实 Broker：

```powershell
\.venv\Scripts\python.exe -m pytest backend/tests/mqtt -q
```

编译检查：

```powershell
\.venv\Scripts\python.exe -m compileall -q `
    backend/common/mqtt `
    backend/tests/mqtt
```

设备没有响应时，按下面顺序检查：

1. 服务端和设备端是否连接到了同一个 Broker。
2. `model`、`did` 和 `down/request` 是否完全一致。
3. 设备端是否订阅了自己的请求 Topic。
4. MQTT 5 设备是否读取 `ResponseTopic` 和 `CorrelationData` 属性。
5. MQTT 3.1.1 设备是否读取 Payload 中的 `response_topic` 和 `correlation_data`。
6. 响应是否原样带回关联数据，且包含有效 `msg_id`。
7. 服务端 Client ID 是否被其他进程复用。
8. 是否因为请求超时、断线或回调队列满而丢失响应处理。

核心原则：

```text
command = 只负责把消息送到设备
request  = 负责把一次设备操作和一次响应关联起来
msg_id   = 负责设备业务幂等
Correlation Data = 负责 MQTT 5 传输层请求-响应匹配
```
