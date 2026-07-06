# Billing API

## 接口列表

1. `POST /api/v1/billing/session/open`
2. `POST /api/v1/billing/usage/debit`
3. `POST /api/v1/billing/session/close`

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

- `session_id`：会话 ID
- `subject_type`：计费主体类型，当前建议固定为 `DEVICE`
- `subject_key`：计费主体标识。当前 `DEVICE` 场景下必须等于 `device_did`
- `device_did`：当前请求设备 DID，必须和认证设备一致
- `started_at`：会话开始时间

### 处理规则

1. 校验设备认证
2. 若 `session_id` 已存在，则校验该会话归属设备并直接返回
3. 若会话不存在，则查找或创建 `u_bill_account`
4. 校验 `u_bill_account.status`
5. 创建 `u_bill_session`

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

### 返回约定

- billing 接口直接返回业务 payload
- 不再额外包一层 `code / msg / data`

### 当前约束

- 如果 `subject_type == "DEVICE"`，则 `subject_key` 必须等于 `device_did`
- `device_did` 必须等于当前认证设备 did
- 如果同一个 `session_id` 已绑定其他设备，请求会被拒绝

### DB 操作与耗时估算

统计口径：

- 只统计 billing 三张表的业务 SQL
- 不包含事务 `BEGIN / COMMIT`
- 不包含设备鉴权额外 DB，因为当前鉴权不查库

分支一：会话已存在

- DB 操作：2 次
- SQL：
  - `select u_bill_session by session_id`
  - `select u_bill_account by account_id for update`
- 预估耗时：`3 ~ 10 ms`

分支二：会话不存在，账户已存在

- DB 操作：3 次
- SQL：
  - `select u_bill_session by session_id`
  - `select u_bill_account by (subject_type, subject_key) for update`
  - `insert u_bill_session`
- 预估耗时：`5 ~ 12 ms`

分支三：会话不存在，账户也不存在

- DB 操作：4 次
- SQL：
  - `select u_bill_session by session_id`
  - `select u_bill_account by (subject_type, subject_key) for update`
  - `insert u_bill_account`
  - `insert u_bill_session`
- 预估耗时：`6 ~ 15 ms`

## 2. usage 扣费

### 请求

`POST /api/v1/billing/usage/debit`

```json
{
  "usage_id": "8e6f6d8d0cfe4f67a4b69c1b9f6f2a10:3:TTS:1",
  "session_id": "8e6f6d8d0cfe4f67a4b69c1b9f6f2a10",
  "turn_no": 3,
  "stage_no": 1,
  "usage_kind": "TTS",
  "usage_token": 84,
  "provider": "azure_push",
  "occurred_at": "2026-07-01T16:00:05+08:00"
}
```

### 字段说明

- `usage_id`：全局唯一的 usage 幂等 ID
- `session_id`：所属会话 ID
- `turn_no`：对话回合号，可为空
- `stage_no`：阶段号，可为空
- `usage_kind`：`ASR / LLM_INPUT / LLM_OUTPUT / TTS`
- `usage_token`：上游已经换算好的 token，必须大于等于 0
- `provider`：来源 provider，可为空
- `occurred_at`：usage 发生时间

### 处理规则

1. 先按 `usage_id` 查 `u_bill_txn`
2. 命中则直接返回第一次成功入账的结果
3. 未命中则锁住 `session + account`
4. 校验认证设备与会话绑定设备一致
5. 直接使用请求里的 `usage_token`
6. 写入一条 `u_bill_txn(change_type=DEBIT)`
7. 更新 `u_bill_account.balance_token`
8. 只有余额扣穿或活跃时间达到阈值时，才更新 `u_bill_session`

### 说明

- 同步热路径只写 `u_bill_txn`
- 不再同步写 `u_bill_usage`
- `provider` 只做来源记录，不参与扣费计算
- 当前 `charge_id` 直接等于 `usage_id`
- 返回状态来自本次 txn 快照，不依赖后续再次查询账户状态
- 非幂等请求只允许 `OPEN` 会话进入扣费逻辑

### 返回

```json
{
  "ok": true,
  "account_id": 10001,
  "usage_id": "8e6f6d8d0cfe4f67a4b69c1b9f6f2a10:3:TTS:1",
  "charge_id": "8e6f6d8d0cfe4f67a4b69c1b9f6f2a10:3:TTS:1",
  "amount_token": 84,
  "balance_after_token": 128416,
  "account_status": "ACTIVE",
  "session_status": "OPEN",
  "should_stop": false
}
```

### 欠费阻断返回

```json
{
  "ok": true,
  "account_id": 10001,
  "usage_id": "8e6f6d8d0cfe4f67a4b69c1b9f6f2a10:3:TTS:1",
  "charge_id": "8e6f6d8d0cfe4f67a4b69c1b9f6f2a10:3:TTS:1",
  "amount_token": 84,
  "balance_after_token": -20,
  "account_status": "BLOCKED",
  "session_status": "BLOCKED",
  "should_stop": true
}
```

### 幂等要求

- `usage_id` 必须全局唯一
- 重复调用同一个 `usage_id` 时，接口必须返回第一次成功入账的结果

### DB 操作与耗时估算

统计口径：

- 只统计 billing 三张表的业务 SQL
- 不包含事务 `BEGIN / COMMIT`
- 不包含嵌套事务 `SAVEPOINT`

分支一：幂等命中

- DB 操作：1 次
- SQL：
  - `select u_bill_txn by usage_id`
- 预估耗时：`2 ~ 6 ms`

分支二：首次扣费，且不更新 session

- DB 操作：4 次
- SQL：
  - `select u_bill_txn by usage_id`
  - `select u_bill_session join u_bill_account for update`
  - `insert u_bill_txn`
  - `update u_bill_account`
- 预估耗时：`6 ~ 15 ms`

分支三：首次扣费，且更新 session

- DB 操作：5 次
- SQL：
  - `select u_bill_txn by usage_id`
  - `select u_bill_session join u_bill_account for update`
  - `insert u_bill_txn`
  - `update u_bill_account`
  - `update u_bill_session`
- 触发场景：
  - 余额扣穿
  - 活跃时间达到刷新阈值
- 预估耗时：`8 ~ 20 ms`

补充说明：

- 同一 `account/session` 上的并发请求会因为行锁串行化，尾延迟会明显放大
- 分散设备场景下，热点不集中时，真实耗时会更接近上面的基础区间

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
- `status`：只能是 `BLOCKED`、`CLOSED` 或 `ABORTED`
- `ended_at`：会话结束时间

### 处理规则

1. 按 `session_id` 加锁查会话
2. 校验认证设备
3. 如果 `ended_at` 已经存在，则直接返回
4. 否则更新 `status / ended_at / last_activity_at`

### 返回

```json
{
  "ok": true,
  "session_id": "8e6f6d8d0cfe4f67a4b69c1b9f6f2a10",
  "session_status": "CLOSED"
}
```

### DB 操作与耗时估算

分支一：会话已经关闭

- DB 操作：1 次
- SQL：
  - `select u_bill_session by session_id for update`
- 预估耗时：`2 ~ 6 ms`

分支二：正常关闭

- DB 操作：2 次
- SQL：
  - `select u_bill_session by session_id for update`
  - `update u_bill_session`
- 预估耗时：`4 ~ 10 ms`

## usage_id 建议格式

统一建议：

`session_id:turn_no:usage_kind:stage_no`

示例：

- `xxx:1:ASR:0`
- `xxx:1:LLM_INPUT:0`
- `xxx:1:LLM_OUTPUT:0`
- `xxx:1:TTS:1`

## usage_kind 约定

- `ASR`
- `LLM_INPUT`
- `LLM_OUTPUT`
- `TTS`
