# Billing Design

## 目标

这一版 billing 只解决 `xiaozhi-server` 当前需要的最小闭环：

1. 打开一个实时计费会话
2. 在会话过程中按真实消耗扣减平台 `token`
3. 余额不足时立即返回 `should_stop`
4. 关闭会话

当前版本不提前引入套餐、订单、发票、月结等概念。

## 计费单位

统一使用平台内部整数 `token` 记账：

- 充值得到 `token`
- 余额使用 `token`
- 每次扣费结果也是 `token`

billing 模块不再负责把毫秒、字符数或第三方 token 换算成平台 token。  
上游在调用 `usage/debit` 之前，必须先完成换算，再把 `usage_token` 传进来。

## 当前表设计

P0 只保留 3 张表：

1. `u_bill_account`
2. `u_bill_session`
3. `u_bill_txn`

### 1. u_bill_account

账户余额快照表。

- 一条记录代表一个计费主体
- 当前推荐主体优先使用 `DEVICE`
- `balance_token` 是当前余额快照
- `status` 控制是否允许进入新会话

### 2. u_bill_session

运行时会话表，用于承接计费上下文。

- 绑定 `account_id`
- 记录 `device_did`
- 维护 `OPEN / BLOCKED / CLOSED / ABORTED`
- `last_activity_at` 只做低频更新，不要求每次 usage 精确落库

它不是账务事实表，也不承载最终扣费明细。

### 3. u_bill_txn

这是同步热路径里的唯一事实表。

一次应扣费的 usage，只写一条 `DEBIT txn`：

- 记录 `usage_id`
- 记录 `charge_id`
- 记录本次扣减的 `delta_token`
- 记录扣减后的 `balance_after_token`
- 记录本次 usage 的 `usage_kind / usage_token / provider`
- 记录入账后的 `account_status_after / session_status_after`

这一版不再同步写 `u_bill_usage`，也不再保留 `u_bill_price`。

## 为什么去掉 u_bill_price

当前计费边界已经收缩为：

- 上游负责把实际消耗换算成平台 `token`
- billing 只负责幂等、扣账、阻断和会话状态
- `provider` 只作为来源审计字段保留在 `u_bill_txn`

既然 billing 不再负责计价，`u_bill_price` 和价格缓存就没有继续保留的必要。

## 为什么去掉 u_bill_usage

`usage/debit` 是高频接口。如果同步写两张事实表：

1. `u_bill_usage`
2. `u_bill_txn`

那么每次请求都会多一次 `insert`，重复请求还要多做读取。

当前需求只要求：

- 扣费正确
- 幂等正确
- 能审计这笔扣费对应的 usage

所以把 usage 信息直接并入 `u_bill_txn` 更合适。

## 热路径

### 1. 打开会话

`session/open` 只做这些事：

1. 校验设备身份
2. 查找或创建 `u_bill_account`
3. 校验 `u_bill_account.status`
4. 创建 `u_bill_session`

### 2. usage 扣费

`usage/debit` 是本模块的高频接口，热路径被压缩为：

1. 先按 `usage_id` 查 `u_bill_txn`，做幂等短路
2. 一次查询锁住 `session + account`
3. 直接使用请求里的 `usage_token`
4. 写入一条 `u_bill_txn(change_type=DEBIT)`
5. 更新 `u_bill_account.balance_token`
6. 只有余额扣穿或活跃时间达到阈值时，才更新 `u_bill_session`

正常路径不再同步写第二张事实表，也不再查询价格表。

### 3. 关闭会话

`session/close` 只更新：

- `status`
- `ended_at`
- `last_activity_at`

## 请求频率与并发模型

这版实现优先保证正确性和稳定性，不承诺未压测前的具体 QPS。

当前并发特征是：

- 幂等命中时，只需要一次 `usage_id` 查询
- 首次扣费时，固定写一条 `u_bill_txn`
- 同一 `account` / 同一 `session` 会通过行锁串行扣费
- 不同 `account` 之间天然分散，可横向放大

也就是说，这版更适合：

- 主体以 `DEVICE` 为主
- 单设备单会话
- 大量分散设备并发写入

如果未来要支持“多个设备共享一个用户账户并高频同时扣费”，再考虑会话预留额度，不放在当前版本内。

## usage_kind 约定

- `ASR`
- `LLM_INPUT`
- `LLM_OUTPUT`
- `TTS`

## 幂等规则

- `usage_id` 必须全局唯一
- 重复调用同一个 `usage_id` 时，直接返回第一次成功入账的结果
- `charge_id` 在当前 `DEBIT` 场景下直接等于 `usage_id`

## 当前不做的事

这些能力不在当前实现范围内：

- 套餐
- 订单支付
- 充值接口
- 发票
- 月结批次
- 异步 usage 审计表
- 会话预留额度
- 在 billing 内部做价格换算
