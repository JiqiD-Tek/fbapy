# Billing API

本文档描述 Billing 模块当前对外暴露的最小接口集。接口路径沿用 `/usage/debit`，但计费语义已经固定为“每个 Turn 只入账一条汇总流水”。

## 接口列表

1. `POST /api/v1/billing/session/open`
2. `POST /api/v1/billing/usage/debit`
3. `POST /api/v1/billing/session/close`

## 通用约定

### 认证

- 所有接口都要求设备认证
- 请求中的 `device_did` 必须与当前认证设备一致

### 返回格式

- 接口直接返回业务 payload
- 不额外包裹 `code / msg / data`

### 幂等

- Billing 统一使用 `usage_id` 作为扣费幂等号
- 同一个 `usage_id` 重复调用时，必须返回第一次成功入账的结果

### 状态字段

- `account_status` 取值：`ACTIVE / BLOCKED`
- `session_status` 取值：`OPEN / BLOCKED / CLOSED / ABORTED`
- `should_stop` 取值规则：当本次流水的 `session_status_after == BLOCKED` 时返回 `true`

## 1. 打开会话

### 请求

`POST /api/v1/billing/session/open`

```json
{
  "session_id": "8e6f6d8d0cfe4f67a4b69c1b9f6f2a10",
  "subject_type": "DEVICE",
  "subject_key": "device_did_xxx",
  "device_did": "device_did_xxx",
  "started_at": "2026-07-01T16:00:00+08:00"
}
```

### 字段说明

- `session_id`：全局唯一会话 ID
- `subject_type`：计费主体类型，当前主路径固定为 `DEVICE`
- `subject_key`：计费主体标识；当 `subject_type=DEVICE` 时必须等于 `device_did`
- `device_did`：当前请求设备 DID，必须与认证设备一致
- `started_at`：会话开始时间

### 处理规则

1. 校验设备认证
2. 按 `session_id` 查询会话
3. 若会话已存在，则校验绑定设备并直接返回
4. 若会话不存在，则按 `(subject_type, subject_key)` 查找或创建账户
5. 校验账户状态为 `ACTIVE`
6. 创建会话，初始状态为 `OPEN`

### 返回

```json
{
  "ok": true,
  "account_id": 10001,
  "balance_token": 128500,
  "account_status": "ACTIVE",
  "session_status": "OPEN"
}
```

### 当前约束

- 同一个 `session_id` 只能绑定一个设备
- 如果 `session_id` 已绑定其他设备，请求必须被拒绝
- `session/open` 不负责充值或解冻账户

## 2. Turn 扣费

### 请求

`POST /api/v1/billing/usage/debit`

```json
{
  "usage_id": "8e6f6d8d0cfe4f67a4b69c1b9f6f2a10:3:TURN",
  "session_id": "8e6f6d8d0cfe4f67a4b69c1b9f6f2a10",
  "turn_no": 3,
  "usage_token": 356
}
```

### 字段说明

- `usage_id`：Turn 级全局唯一幂等 ID，推荐格式 `session_id:turn_no:TURN`
- `session_id`：所属会话 ID
- `turn_no`：回合号
- `usage_token`：上游 Metering 汇总后的 Turn 总消耗，必须大于等于 `0`

### 处理规则

1. 按 `usage_id` 查询 `u_bill_txn`
2. 若命中，则直接返回第一次成功入账的结果
3. 若未命中，则锁定会话和账户
4. 校验认证设备与会话绑定设备一致
5. 校验只有 `OPEN` 状态的会话才能进入新扣费
6. 用 `usage_token` 计算本次扣费结果
7. 写入一条 `u_bill_txn(change_type=DEBIT)`
8. 更新 `u_bill_account.balance_token`
9. 若本次扣费后余额小于等于 `0`，则将账户和会话都标记为 `BLOCKED`
10. 若未阻断，则只在达到活跃时间刷新阈值时更新 `u_bill_session.last_activity_at`

### 语义说明

- 一次 Turn 只写一条 `u_bill_txn`
- Billing 不接收 `usage_kind`
- Billing 不按 ASR / LLM / TTS 分别入账
- `usage_token` 由上游 Metering 先完成换算和汇总后传入
- 非幂等请求只允许 `OPEN` 会话进入扣费逻辑
- `BLOCKED` 会话只允许返回既有幂等结果，不能继续新扣费

### 正常返回

```json
{
  "ok": true,
  "account_id": 10001,
  "usage_id": "8e6f6d8d0cfe4f67a4b69c1b9f6f2a10:3:TURN",
  "amount_token": 356,
  "balance_after_token": 128144,
  "account_status": "ACTIVE",
  "session_status": "OPEN",
  "should_stop": false
}
```

### 阻断返回

```json
{
  "ok": true,
  "account_id": 10001,
  "usage_id": "8e6f6d8d0cfe4f67a4b69c1b9f6f2a10:3:TURN",
  "amount_token": 356,
  "balance_after_token": -20,
  "account_status": "BLOCKED",
  "session_status": "BLOCKED",
  "should_stop": true
}
```

### 幂等要求

- `usage_id` 必须全局唯一
- 对同一个 `usage_id` 的重复调用，接口必须返回第一次成功入账的结果
- 幂等命中时不重复扣减余额，也不重复变更会话状态

## 3. 关闭会话

### 请求

`POST /api/v1/billing/session/close`

```json
{
  "session_id": "8e6f6d8d0cfe4f67a4b69c1b9f6f2a10",
  "status": "CLOSED",
  "ended_at": "2026-07-01T16:00:10+08:00"
}
```

### 字段说明

- `session_id`：会话 ID
- `status`：关闭后的会话状态，只允许 `BLOCKED / CLOSED / ABORTED`
- `ended_at`：会话结束时间

### 处理规则

1. 按 `session_id` 加锁查询会话
2. 校验认证设备与会话绑定设备一致
3. 若会话已结束，则直接返回当前状态
4. 否则更新 `status / ended_at / last_activity_at`

### 返回

```json
{
  "ok": true,
  "session_id": "8e6f6d8d0cfe4f67a4b69c1b9f6f2a10",
  "session_status": "CLOSED"
}
```

## 调用方适配要点

调用方需要按当前接口口径完成适配：

- 用 `usage_id` 替代旧的 `charge_id`
- 不再传 `stage_no`
- 不再传 `usage_kind`
- 不再传 `provider`
- 不再传 `occurred_at`
- 上游先汇总 ASR / LLM / TTS 成本，再调用 `usage/debit`

## usage_id 建议格式

统一建议：

```text
{session_id}:{turn_no}:TURN
```

示例：

- `xxx:1:TURN`
- `xxx:2:TURN`
