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

### 处理规则

1. 校验设备认证
2. 查找或创建 `u_bill_account`
3. 校验 `u_bill_account.status`
4. 创建 `u_bill_session`

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

### 处理规则

1. 先按 `usage_id` 查 `u_bill_txn`
2. 命中则直接返回第一次成功入账的结果
3. 未命中则锁住 `session + account`
4. 直接使用请求里的 `usage_token`
5. 写入一条 `u_bill_txn(change_type=DEBIT)`
6. 更新 `u_bill_account.balance_token`
7. 只有余额扣穿或活跃时间达到阈值时，才更新 `u_bill_session`

### 说明

- 同步热路径只写 `u_bill_txn`
- 不再同步写 `u_bill_usage`
- `provider` 只做来源记录，不参与扣费计算
- `charge_id` 当前直接等于 `usage_id`
- 返回状态来自本次 txn 快照，不依赖后续再次查询账户状态

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

### 返回

```json
{
  "ok": true,
  "session_id": "8e6f6d8d0cfe4f67a4b69c1b9f6f2a10",
  "session_status": "CLOSED"
}
```

## usage_id 建议格式

统一建议为：

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

## 幂等要求

- `usage_id` 必须全局唯一
- 重复调用同一个 `usage_id` 时，接口必须返回第一次成功入账的结果
- `charge_id` 在当前 `DEBIT` 场景下可直接等于 `usage_id`
