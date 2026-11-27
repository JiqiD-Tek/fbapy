# 设备每日共享 AI 用量

按设备 DID 和业务日期累计。CHAT、STORY 共用每日额度和相同的计算方法；
`u_device_usage.quantity` 是当日累计用量，`u_device_usage_event.quantity` 是本次用量。
`event_type` 只标记事件来源。

## 换算公式

1 元估算成本对应 1,000,000 用量单位，全部采用整数运算。

| 项目       | 单价          | 换算系数         |
|----------|-------------|--------------|
| 语音识别     | 0.07 元/分钟   | 70,000 单位/分钟 |
| 大模型输入和输出 | 0.003 元/千字符 | 3 单位/字符      |
| 文本转语音    | 0.3 元/千字符   | 300 单位/字符    |

两种业务均提供 `asr_characters`（识别字符数）和 `tts_characters`（合成字符数）。
两个参数均为非负整数，且不能同时为 0，无需上传文本。
大模型输入量按识别字符数估算，输出量按合成字符数估算。
ASR 原始单价按分钟计费，仅凭字符数无法得知实际识别时长，因此通过可配置语速估算：

```text
N = asr_characters
M = tts_characters
R = 每分钟识别字符数，默认 300

本次用量 = 向上取整(N × 70000 / R + (N + M) × 3 + M × 300)
剩余额度 = max(每日共享额度 - 当日累计用量, 0)
```

例如识别 300 字、合成 300 字，消耗 161,800 单位，约 0.1618 元。
识别 100 字、合成 100 字，消耗 53,934 单位。
字符数使用 Python `len()` 的计数方式；仅在最终总量向上取整一次。

此算法用于统一额度估算，不是供应商账单核算。提示词、历史上下文、音频静音部分
和模型内部用量未包含在这两个参数内。

## 配置

```dotenv
# 示例：每日 100 万单位，即约 1 元估算成本；按产品实际额度设置
DEVICE_DAILY_AI_QUOTA=1000000
ASR_CHARACTERS_PER_MINUTE=300
```

未设置每日额度时不限制，查询额度返回 `null`；设置为 0 时禁止提交新的设备剧本任务。
语速必须大于 0。每日用量按服务端配置时区的日期独立计算。

## 调用方法

```python
quantity = DeviceUsageCalculator.calculate_quantity(
    asr_characters=100,
    tts_characters=100,
)
```

## 接口

两个接口通过设备认证获取 DID，无需在请求里提供 DID。

`GET /api/v1/terminal/device/usage` 的标准响应 `data` 包含：

```json
{
  "did": "设备 DID",
  "usage_date": "2026-11-27",
  "daily_quota": 1000000,
  "quantity": 161800,
  "remaining_quantity": 838200
}
```

`POST /api/v1/terminal/device/usage` 的请求：

```json
{
  "event_type": "CHAT",
  "event_key": "本次上报的唯一标识",
  "asr_characters": 100,
  "tts_characters": 100
}
```

STORY 使用相同参数，仅将 `event_type` 改为 `STORY`。
响应返回更新后的当日累计用量和剩余额度。调用方必须上报本次增量，
同一事件重试时保持同一个 `event_key`，避免重复累计。

内置玩偶剧本任务生成成功后自动统计：`asr_characters` 使用用户要求的字符数，
`tts_characters` 使用生成台词文本的字符数总和，任务 ID 作为事件标识。
文字输入的管理操作按同一估算规则处理；无设备 DID 的后台任务不计入设备用量。
普通 `synthesize_story` 不参与统计。

查询只返回快照，不预占额度。AI 对话服务应在消费前和持续对话过程中检查
`remaining_quantity`，为 0 时停止继续消费。设备剧本提交入口也会检查剩余额度。
记录接口如实累计已产生的消耗，即使超过额度也不丢弃用量；剩余额度最低为 0。
同时发起的任务可能超过总额度，本版不提供额度预占。

## 数据库结构切换

`u_device_usage` 删除 `chat_seconds`、`story_count`，改为 `quantity BIGINT NOT NULL`，
新建记录默认 0。事件表的 `quantity` 改为统一用量含义。

已有数据库必须同步结构后再使用新代码；模型修改不会自动修改已存在的表。
旧事件的秒数、次数缺少识别字符数和合成字符数，无法据此还原新用量。
旧数据不能直接混入新用量，应在切换时单独归档。当前仓库没有可衔接的 Alembic
历史版本，本次未执行数据库迁移。
