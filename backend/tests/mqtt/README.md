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
from backend.common.mqtt import MQTTClient, MQTTConfig, MQTTVersion
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

## 3. Topic 协议

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

## 4. 两种消息语义

### 4.1 `down/command`：只发布，不等业务响应

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

### 4.2 `down/request`：发布并等待设备响应

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

## 5. MQTT 5 请求-响应流程

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

## 6. MQTT 3.1.1 兼容流程

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

## 7. 请求、响应和幂等字段

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

## 8. 为什么响应不会串数据

正常实现下，响应通过三层信息隔离：

1. **设备 Topic 隔离**：`device-001` 和 `device-002` 使用不同的 `down/request` Topic，设备应只订阅自己的精确 Topic。
2. **服务端响应 Topic 隔离**：每个 MQTTClient 使用唯一 Client ID 和专用响应 Topic，设备按请求中的 Response Topic 返回。
3. **Correlation Data 隔离**：同一设备的并发请求使用不同关联数据，响应不依赖到达顺序。

仍然需要注意：

- 每个服务端进程必须使用唯一 Client ID；复用 Client ID 会导致 Broker 踢掉旧连接。
- 设备必须原样返回 Correlation Data。
- pending Future 位于进程内存中，断线或进程退出后不能自动跨实例恢复。
- 如果需要跨进程接管请求状态，应使用共享状态存储或任务队列重新设计。

## 9. 服务端通用设备请求 API

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

## 10. 并发、超时和可靠性

`MQTTClient` 当前包含以下保护机制：

| 机制                      | 作用                               |
|-------------------------|----------------------------------|
| 全局 pending Semaphore    | 限制同时进行中的 `request()` 数量          |
| `max_inflight_messages` | 限制 Paho 同时发送中的消息数量               |
| `max_queued_messages`   | 限制 Paho 本地排队消息数量                 |
| 单一 request deadline     | Semaphore、订阅等待、发布确认和响应等待共用一个截止时间 |
| `on_publish` + Future   | 不使用线程池阻塞等待发布确认                   |
| SUBACK MID 校验           | 只接受当前响应 Topic 订阅对应的 SUBACK       |
| 断线清理 pending            | 连接断开时结束等待中的发布和请求 Future          |
| 回调分片队列                  | 按 Topic 或设备 DID 分配回调，减少互相阻塞      |

边界行为：

- `publish()` 成功只代表 MQTT 发布确认成功，不代表设备业务成功。
- `request()` 超时不一定代表设备没有执行，业务动作必须依赖 `msg_id` 幂等。
- 回调队列达到上限时会丢弃普通业务回调并记录日志，应结合容量、消费速度和监控调优。
- 断线后当前进程中的请求会失败，不会自动重放设备动作。
- 当前没有做相同在途请求合并，也没有设备级并发信号量。

## 11. 启动模拟服务

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

## 12. 自动化测试和排查

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
