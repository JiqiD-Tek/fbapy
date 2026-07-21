# Billing Design

## 1. 模块定位

Billing 模块负责 `xiaozhi-server` 实时会话中的最小计费闭环，目标是：

1. 管理计费账户与余额快照
2. 控制计费会话的打开、阻断和关闭
3. 按对话轮次（Turn）执行幂等扣费
4. 在余额耗尽时返回阻断信号

当前版本明确不覆盖以下能力：

- 套餐管理
- 充值下单
- 发票
- 月结
- 价格表管理
- 分项账务明细（ASR / LLM / TTS）
- 独立的 usage 事实表

模块设计原则是先保证账务正确性和接口语义稳定，再考虑性能优化和能力扩展。

## 2. 核心计费口径

### 2.1 入账粒度

Billing 的入账粒度固定为一次对话轮次（Turn）：

- 一轮对话只写一条 `u_bill_txn`
- 一次请求只处理一个 `usage_id`
- 当前扣费场景下 `change_type` 固定为 `DEBIT`

### 2.2 幂等标识

`usage_id` 是 Turn 级唯一幂等标识，推荐格式：

```text
{session_id}:{turn_no}:TURN
```

例如：

- `8e6f6d8d0cfe4f67a4b69c1b9f6f2a10:1:TURN`
- `8e6f6d8d0cfe4f67a4b69c1b9f6f2a10:2:TURN`

### 2.3 消耗计算

`usage_token` 由上游 Metering 计算后传入，Billing 不负责换算。

上游职责包括：

- 统计 ASR 时长
- 统计 LLM 输入输出 Token
- 统计 TTS 字符数
- 按价格规则换算为平台 Token
- 汇总为 Turn 级 `usage_token`

Billing 只消费汇总结果，不接收也不存储 ASR / LLM / TTS 分项明细。

### 2.4 余额变动

账务真实变动以 `delta_token` 为准：

- 扣费场景下 `delta_token = -usage_token`
- `usage_token` 表示本轮消耗
- `balance_after_token` 表示本次入账后的余额快照

`usage_token` 保留在流水表中，是为了便于接口返回、问题排查和按 Turn 查询消耗；真正的账务变动值仍然是 `delta_token`。

## 3. 数据模型

P0 版本只使用三张核心表：

1. `u_bill_account`
2. `u_bill_session`
3. `u_bill_txn`

其中：

- `u_bill_account` 是账户余额快照
- `u_bill_session` 是运行时会话关系表，不是账务真相
- `u_bill_txn` 是同步热路径中的唯一事实表

### 3.1 `u_bill_account`

用于承载计费主体和当前余额快照。

| 字段              | 说明                          |
|-----------------|-----------------------------|
| `subject_type`  | 主体类型，当前主路径固定为 `DEVICE`      |
| `subject_key`   | 主体标识，设备场景下等于 `device_did`   |
| `balance_token` | 当前余额快照                      |
| `status`        | 账户状态，当前为 `ACTIVE / BLOCKED` |
| `created_time`  | 创建时间                        |
| `updated_time`  | 更新时间                        |

约束：

- 唯一键：`(subject_type, subject_key)`

说明：

- 当前版本没有独立充值链路，这张表只负责余额快照和准入控制

### 3.2 `u_bill_session`

用于记录设备会话与计费账户的关系。

| 字段                 | 说明                                          |
|--------------------|---------------------------------------------|
| `session_id`       | 全局唯一会话 ID                                   |
| `account_id`       | 关联账户 ID                                     |
| `device_did`       | 设备 DID                                      |
| `started_at`       | 会话开始时间                                      |
| `status`           | 会话状态，支持 `OPEN / BLOCKED / CLOSED / ABORTED` |
| `last_activity_at` | 最近活跃时间                                      |
| `ended_at`         | 会话结束时间                                      |
| `created_time`     | 创建时间                                        |
| `updated_time`     | 更新时间                                        |

约束：

- 唯一键：`session_id`

说明：

- `u_bill_session` 是运行时控制表，不承担账务真相
- `last_activity_at` 不要求每轮都更新，只在达到刷新阈值或会话状态变化时更新

### 3.3 `u_bill_txn`

账务流水表，是 Billing 同步热路径中的唯一事实表。

| 字段                     | 必填 | 说明                                         |
|------------------------|----|--------------------------------------------|
| `usage_id`             | 是  | Turn 级幂等 ID，推荐格式 `session_id:turn_no:TURN` |
| `account_id`           | 是  | 账户 ID                                      |
| `session_id`           | 是  | 会话 ID                                      |
| `turn_no`              | 是  | 回合号                                        |
| `change_type`          | 是  | 当前固定为 `DEBIT`                              |
| `usage_token`          | 是  | 本轮汇总消耗                                     |
| `delta_token`          | 是  | 余额变动值，扣费时为负数                               |
| `balance_after_token`  | 是  | 变动后余额快照                                    |
| `account_status_after` | 是  | 入账后账户状态                                    |
| `session_status_after` | 是  | 入账后会话状态                                    |
| `created_time`         | 是  | 入账时间                                       |

索引：

- 唯一键：`usage_id`
- 普通索引：`(account_id, created_time)`
- 普通索引：`(session_id, turn_no)`

## 4. 字段取舍

当前 schema 中不再保留以下字段：

| 字段            | 原因                                       |
|---------------|------------------------------------------|
| `charge_id`   | 与 `usage_id` 语义重复，统一只保留 `usage_id` 作为幂等键 |
| `stage_no`    | 当前不做分阶段扣费，一轮 Turn 只入账一次                  |
| `usage_kind`  | 当前入账粒度固定为 Turn，无需再在流水中区分 `TURN`          |
| `provider`    | Billing 不按 provider 计价，来源追溯放在上游 Metering |
| `occurred_at` | 同步入账场景下直接使用 `created_time` 表示入账时间        |

保留 `session_id` 和 `turn_no` 的原因：

- 支持按会话查看扣费历史
- 支持按回合定位具体流水
- 避免依赖解析 `usage_id` 才能完成查询

## 5. 核心接口流程

### 5.1 打开会话 `session/open`

处理流程：

1. 校验 `device_did` 与当前认证设备一致
2. 按 `session_id` 查询会话
3. 如果会话已存在，校验绑定设备后直接返回
4. 如果会话不存在，则查找或创建账户
5. 校验账户状态必须为 `ACTIVE`
6. 创建会话，初始状态为 `OPEN`

当前约束：

- `subject_type` 当前主路径固定使用 `DEVICE`
- 当 `subject_type == DEVICE` 时，`subject_key` 必须等于 `device_did`

### 5.2 扣费 `usage/debit`

处理流程：

1. 按 `usage_id` 查询流水，先做幂等检查
2. 若已存在流水，直接返回第一次成功入账的结果
3. 若不存在，则锁定会话和账户
4. 校验认证设备与会话绑定设备一致
5. 校验只有 `OPEN` 状态的会话才允许进入新扣费
6. 使用请求中的 `usage_token` 执行扣费
7. 写入一条 `u_bill_txn`
8. 更新账户余额快照
9. 若本次扣费后余额小于等于 0，则将账户和会话状态置为 `BLOCKED`
10. 若未阻断，则按活跃时间刷新阈值决定是否更新 `last_activity_at`

关键规则：

- 非幂等请求只允许 `OPEN` 会话进入扣费逻辑
- `BLOCKED` 会话只允许返回既有幂等结果，拒绝新的扣费请求
- `should_stop` 由本次流水的 `session_status_after` 决定
- 并发重复请求以 `usage_id` 唯一键和数据库事务共同保证幂等

### 5.3 关闭会话 `session/close`

处理流程：

1. 锁定并查询会话
2. 校验认证设备身份
3. 若会话已结束，则直接返回当前状态
4. 否则更新 `status / ended_at / last_activity_at`

说明：

- 关闭接口用于显式结束会话
- 关闭后的状态由调用方传入，当前允许 `BLOCKED / CLOSED / ABORTED`

## 6. 状态语义

### 6.1 账户状态

- `ACTIVE`：账户可正常打开会话并继续扣费
- `BLOCKED`：账户已被阻断，通常由扣费后余额耗尽触发

### 6.2 会话状态

- `OPEN`：会话可继续扣费
- `BLOCKED`：会话被阻断，只允许幂等重放
- `CLOSED`：会话正常关闭
- `ABORTED`：会话异常结束

### 6.3 阻断信号

调用方应使用返回结果中的 `should_stop` 作为停止当前会话的直接信号。

语义约定：

- `should_stop = false`：本轮扣费后会话仍可继续
- `should_stop = true`：本轮扣费后会话已进入 `BLOCKED`

## 7. 并发与性能模型

### 7.1 幂等命中

幂等命中时只需要：

- 读取一次 `u_bill_txn`
- 不更新账户
- 不更新会话

这条路径没有写操作，性能最好。

### 7.2 首次扣费

首次扣费通过数据库行锁串行化同一会话/账户上的并发请求：

- 锁定 `u_bill_session`
- 锁定对应 `u_bill_account`
- 写入 `u_bill_txn`
- 更新 `u_bill_account`
- 仅在必要时更新 `u_bill_session`

设计目标：

- 优先保证账务绝对正确
- 当前不引入预扣额度
- 当前不引入异步扣费

如果后续出现多设备共享同一账户且高频并发扣费的场景，再考虑额度预留或更复杂的账户并发模型。

## 8. 与 Metering 的边界

### Metering 负责

- 统计 ASR / LLM / TTS 原始消耗
- 按价格规则换算为平台 Token
- 汇总为 Turn 级 `usage_token`

### Billing 负责

- 账户管理与余额快照
- 幂等扣费
- 会话状态控制
- 阻断信号返回
- 流水记录与查询

### Billing 不负责

- 价格管理
- 汇率换算
- 分项明细存储
- 历史价格回放

## 9. 落地注意事项

代码侧需要同步更新以下位置，确保实现和文档一致：

- `backend/app/cloud/model/billing.py`
- `backend/app/cloud/schema/billing.py`
- `backend/app/cloud/service/billing_service.py`

调用方需要按新口径适配请求和响应：

- 统一使用 `usage_id` 作为幂等号
