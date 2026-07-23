# 小智 Billing 设计

## 1. 模块定位

Billing 模块只负责小智服务的一轮对话扣费闭环：

1. 维护设备计费账户和余额快照。
2. 按一轮对话，也就是 turn，写入一条账务流水。
3. 对重复上报的同一轮扣费请求做幂等处理。

当前版本不再管理运行时会话生命周期，所以不需要 `u_bill_session`，也不再提供 session open/close 接口。`session_id` 和
`sentence_id` 都由小智 WebSocket 运行时生成并传入 Billing。

当前只覆盖 turn 级扣费，不覆盖以下能力：

- 套餐和价格表管理
- 充值、退款、调账
- 发票、月结、对账单
- ASR / LLM / TTS 分项明细落库
- 独立 usage 事实表

## 2. 小智运行时 ID 语义

Billing 的幂等和查询依赖小智运行时传入的两个 ID：

| 字段            | 粒度            | 生成时机                                               | Billing 用途                   |
|---------------|---------------|----------------------------------------------------|------------------------------|
| `session_id`  | WebSocket 连接级 | `ConnectionRuntime` 创建时生成 `SessionContext`，连接内固定不变 | 按连接查询账务流水                    |
| `sentence_id` | 对话轮次级         | 每次进入 `_begin_chat_turn()` 时生成                      | 与 `session_id` 组成 turn 扣费幂等键 |

### 正常对话

1. WebSocket 连接建立，创建 `ConnectionRuntime`。
2. `SessionContext` 生成并固定 `session_id`。
3. 用户语音被识别为文本。
4. 如果不是 `asr_only`，进入 `_launch_chat_turn()` 和 `_begin_chat_turn()`。
5. 本轮生成新的 `sentence_id`。
6. 同一轮里的 LLM、工具调用、assistant 文本、TTS 输出复用同一个 `sentence_id`。
7. 下一轮重新生成新的 `sentence_id`，但 `session_id` 不变，直到连接断开。

### ASR-only 模式

`handshake.asr_only = True` 时，只走 STT 输出，不进入完整聊天 turn，也不会生成 `sentence_id`。这种请求不应调用 turn 级
Billing 扣费接口。

### idle_timeout_close

空闲超时关闭会走 `_launch_chat_turn(..., turn_kind=IDLE_TIMEOUT_CLOSE)`，仍然会进入 `_begin_chat_turn()` 并生成
`sentence_id`。因此它是一个由超时触发的完整 turn，可以按同一套 `session_id + sentence_id` 规则处理。

一句话总结：

- `session_id` = 一条 WebSocket 连接的身份。
- `sentence_id` = 这条连接里某一轮对话的身份。

## 3. 数据模型

当前只保留两张表：

1. `u_bill_account`
2. `u_bill_txn`

`u_bill_account` 是账户余额快照，`u_bill_txn` 是不可变账务流水。运行时连接状态由小智服务负责，不再落 `u_bill_session`。

### 3.1 `u_bill_account`

| 字段              | 必填 | 说明                           |
|-----------------|----|------------------------------|
| `id`            | 是  | 主键                           |
| `subject_type`  | 是  | 计费主体类型，当前固定为 `DEVICE`        |
| `subject_key`   | 是  | 计费主体标识，当前为设备 `did`           |
| `balance_token` | 是  | 当前余额快照，单位 token              |
| `status`        | 是  | 账户状态，当前支持 `ACTIVE / BLOCKED` |
| `created_time`  | 是  | 创建时间                         |
| `updated_time`  | 否  | 更新时间                         |

约束：

- 唯一键：`(subject_type, subject_key)`

说明：

- 小智设备调用 Billing 时不需要传 `device_did`、`subject_type`、`subject_key`。
- 设备身份来自 `DependsDeviceAuth`，服务端用认证上下文里的 `auth_ctx.did` 定位 `DEVICE` 账户。

### 3.2 `u_bill_txn`

| 字段              | 必填 | 说明                        |
|-----------------|----|---------------------------|
| `id`            | 是  | 主键                        |
| `account_id`    | 是  | 计费账户 ID                   |
| `session_id`    | 是  | 连接级 ID，来自小智运行时            |
| `sentence_id`   | 是  | 轮次级 ID，来自小智运行时            |
| `amount_token`  | 是  | 本次变动金额，统一为正数              |
| `balance_token` | 是  | 本次变动后的余额快照                |
| `change_type`   | 是  | 当前主路径固定为 `DEBIT`，方向由该字段表示 |
| `created_time`  | 是  | 流水创建时间                    |

约束和索引：

- 唯一键：`(session_id, sentence_id)`
- 普通索引：`(account_id, created_time)`
- 普通索引：`(session_id, created_time)`

说明：

- 一轮对话只写一条 `u_bill_txn`。
- 同一轮里的 ASR、LLM、工具调用、TTS 不再分别写账务流水，由上游先聚合并折算成一个 `amount_token`。
- `amount_token` 始终为正数，余额加减方向由 `change_type` 决定。当前 `DEBIT` 场景表示扣减。
- 幂等键使用 `(session_id, sentence_id)`，不再额外构造 `usage_id`。

## 4. 不再保留或已改名的字段和表

| 名称                     | 处理                 | 原因                                                                    |
|------------------------|--------------------|-----------------------------------------------------------------------|
| `u_bill_session`       | 删除                 | 小智运行时已经管理连接生命周期，Billing 不再重复维护 session 状态                             |
| `usage_id`             | 删除                 | `sentence_id` 已经是 turn 级 ID，结合 `session_id` 可以直接作为幂等键                 |
| `turn_no`              | 删除                 | 小智运行时没有依赖 turn_no，查询和幂等都使用 `sentence_id`                              |
| `usage_token`          | 改为 `amount_token`  | Billing 接口接收的是折算后的扣费金额，不是 ASR / LLM / TTS 原始 usage                    |
| `delta_token`          | 改为 `amount_token`  | `delta` 容易被理解为带符号变动值；当前使用正数金额，方向交给 `change_type`                      |
| `balance_after_token`  | 改为 `balance_token` | 在流水表语境下就是本次流水后的余额快照，字段名可以更短                                           |
| `session_status_after` | 删除                 | Billing 不再维护 session 状态                                               |
| `account_status_after` | 删除                 | 当前扣费后的账户状态可由 `balance_token <= 0` 推导，账户当前状态放在 `u_bill_account.status` |
| `stage_no`             | 删除                 | 当前不做分阶段扣费                                                             |
| `usage_kind`           | 删除                 | 当前账务入账粒度固定为 turn                                                      |
| `provider`             | 删除                 | provider 级消耗由上游 Metering 管理                                           |
| `occurred_at`          | 删除                 | 同步入账场景直接使用 `created_time`                                             |

如果未来需要审计人工封禁、复杂状态流转、历史状态回放，可以再把 `account_status_after` 作为流水状态快照加回来。当前版本为了保持表结构简单，不提前存这个冗余字段。

## 5. 接口

Billing 接口通过小智资源入口暴露：

```text
POST /api/v1/resource/xiaozhi/billing/debit
```

请求：

```json
{
  "session_id": "f78b773581494f8e8a603b8194de7abc",
  "sentence_id": "a263ecbaa9f34e77a903fd5e195b68dd",
  "amount_token": 128
}
```

响应：

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "account_id": 1,
    "session_id": "f78b773581494f8e8a603b8194de7abc",
    "sentence_id": "a263ecbaa9f34e77a903fd5e195b68dd",
    "amount_token": 128,
    "balance_token": 872,
    "account_status": "ACTIVE"
  }
}
```

处理流程：

1. 按认证设备 `auth_ctx.did` 获取或创建 `DEVICE` 账户，并锁定账户行。
2. 如果账户状态不是 `ACTIVE`，先按 `(session_id, sentence_id)` 查询已有流水；命中则返回历史扣费结果，未命中则拒绝新的扣费请求。
3. 计算本次扣费金额 `amount_token` 和扣费后余额 `balance_token`。
4. 写入一条 `u_bill_txn`。
5. 如果写入撞到 `(session_id, sentence_id)` 唯一键，说明是并发或重试请求，回查已有流水并返回历史扣费结果。
6. 更新 `u_bill_account.balance_token`。
7. 如果 `balance_token <= 0`，将账户状态置为 `BLOCKED`。

旧接口不再保留：

- `POST /api/v1/resource/xiaozhi/billing/session/open`
- `POST /api/v1/resource/xiaozhi/billing/session/close`
- `POST /api/v1/resource/xiaozhi/billing/usage/debit`

## 6. Metering 边界

上游 Metering 负责：

- 统计 ASR 原始消耗。
- 统计 LLM 输入和输出 token。
- 统计 TTS 字符数或音频消耗。
- 按当前价格规则换算成平台 token。
- 聚合成 turn 级扣费金额 `amount_token`。

Billing 负责：

- 账户余额快照。
- turn 级幂等扣费。
- 流水记录。

Billing 不负责：

- ASR / LLM / TTS 分项明细存储。
- 价格规则和 provider 计费。
- 历史价格回放。
- session 生命周期管理。

## 7. 相关聊天记录接口

聊天内容历史和账务流水分开存储。小智保存聊天记录使用：

```text
POST /api/v1/resource/xiaozhi/turn/chat
```

该接口写入 `u_device_chat`，用于后期按设备、宝宝、玩偶查询聊天记录；Billing 只保存扣费事实，不保存用户输入和回复内容。
