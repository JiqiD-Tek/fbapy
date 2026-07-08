# Billing Design

## 目标

当前 billing 只解决 `xiaozhi-server` 实时会话里的最小计费闭环：

1. 打开计费会话
2. 会话过程中按 `usage_token` 扣费
3. 余额不足时返回 `should_stop`
4. 关闭会话

当前实现不包含这些能力：

- 套餐
- 充值下单
- 发票
- 月结
- 独立价格表
- 独立 usage 事实表

## 当前代码边界

### 统一计量单位

billing 内部统一使用整数 `token`：

- 账户余额是 `balance_token`
- 本次扣费是 `usage_token`
- 流水变动是 `delta_token`

billing 不负责把毫秒、字符数、第三方 token 再换算成平台 token。  
上游在调用 `usage/debit` 之前，必须先完成换算。

### 当前接口约束

当前代码仍然保留 `subject_type` 和 `subject_key` 这两个入参，但主路径按 `DEVICE` 使用。

如果 `subject_type == 'DEVICE'`，则必须满足：

- `subject_key == device_did`
- `device_did == 当前认证设备 did`

也就是说，当前代码虽然保留了“通用计费主体”结构，但实际推荐用法仍然是“设备账户”。

### usage 类型

当前只支持 4 种 `usage_kind`：

- `ASR`
- `LLM_INPUT`
- `LLM_OUTPUT`
- `TTS`

## 表设计

P0 只保留 3 张表：

1. `u_bill_account`
2. `u_bill_session`
3. `u_bill_txn`

### 1. u_bill_account

账户快照表，用来承载计费主体和当前余额。

核心字段：

- `subject_type`
- `subject_key`
- `balance_token`
- `status`
- `created_time`
- `updated_time`

说明：

- 当前唯一键是 `(subject_type, subject_key)`
- `status` 目前只区分 `ACTIVE / BLOCKED`
- 当前代码没有单独的充值逻辑，这张表主要承担余额快照和准入控制

### 2. u_bill_session

运行时会话表，用来承载设备会话与账户关系，不承担账务真相。

核心字段：

- `session_id`
- `account_id`
- `device_did`
- `started_at`
- `status`
- `last_activity_at`
- `ended_at`
- `created_time`
- `updated_time`

说明：

- `session_id` 全局唯一
- `status` 支持 `OPEN / BLOCKED / CLOSED / ABORTED`
- `last_activity_at` 不是每次 usage 都更新，只在需要时更新

### 3. u_bill_txn

账务流水表，是当前同步热路径中的唯一事实表。

核心字段：

- `charge_id`
- `account_id`
- `change_type`
- `delta_token`
- `balance_after_token`
- `account_status_after`
- `session_status_after`
- `usage_id`
- `session_id`
- `turn_no`
- `stage_no`
- `usage_kind`
- `usage_token`
- `provider`
- `occurred_at`
- `created_time`

说明：

- 当前代码只写 `DEBIT`
- `charge_id` 当前直接等于 `usage_id`
- 真正承担幂等唯一约束的是 `usage_id`
- `u_bill_txn` 不继承 `DateTimeMixin`，只保留 `created_time`
- 这是不可变流水，不设计 `updated_time`

## 为什么不保留 u_bill_usage

`usage/debit` 是高频接口。当前需求只要求：

- 扣费正确
- 幂等正确
- 能追溯每一笔 usage 对应的扣费

如果再同步写一张 `u_bill_usage`，每次首次扣费都会多一条事实写入，重复请求也会引入更多判断成本。

当前代码的做法是把 usage 相关字段直接并入 `u_bill_txn`：

- `usage_kind`
- `usage_token`
- `provider`
- `turn_no`
- `stage_no`
- `occurred_at`

这样可以把高频路径收敛到一张事实表。

## 上游 metering 与定价

### 3.1 职责边界

当前 billing 已经不负责计价。

以下“定价策略”只属于上游 metering 配置口径，不属于 billing 热路径内置逻辑。  
billing 仍然只接收已经换算完成的 `usage_token`。

职责边界是：

- 上游负责换算出 `usage_token`
- billing 负责幂等、扣账、阻断、会话状态
- `provider` 只做来源记录，不参与扣费计算

因此当前代码不需要：

- `u_bill_price`
- 价格缓存
- 历史价格回放

### 3.2 定价策略

平台售价策略固定为：

- 先确认云厂商真实采购成本
- 再按产品策略加价
- 当前推荐基线是“云成本约上浮 10%”
- 不允许拍脑袋把 `AUDIO_MS / PROVIDER_TOKEN / TEXT_CHAR` 直接映射成平台 token

### 3.3 代码默认资源与当前计费基线

当前仓库里的“代码默认资源”和“当前 billing 使用的计费基线”不是一个概念，不能混写。

当前代码中可直接看到的默认资源如下：

- `ASR`：`volc.bigasr.sauc.duration`
- `LLM`：默认 chat 模型 `doubao-seed-2-0-lite-260215`
- `LLM`：默认 story 模型 `doubao-seed-2-0-pro-260215`
- `TTS`：流式默认资源 `seed-tts-2.0`
- `TTS`：长文本默认资源 `seed-icl-2.0`

本节下面的“当前推荐参考价”按当前项目准备采用的计费基线模型书写：

- `ASR`：`DoubaoStreamASRProvider + volc.bigasr.sauc.duration`
- `LLM`：`OpenAILLMProvider + doubao-seed-2-0-mini-260428`
- `TTS`：`HuoshanStreamTTSProvider + seed-icl-2.0`

也就是说，这里描述的是 `billing.metering.rules` 的配置口径，不等同于“代码里所有地方的默认值”。

### 3.4 当前推荐参考价

当前推荐参考价如下：

| 服务         | 云成本参考                               | 平台目标售价                 | metering 规则                          |
|------------|-------------------------------------|------------------------|--------------------------------------|
| ASR        | `4.5 RMB / 小时` 公开刊例保守口径             | `4.95 RMB / 小时`        | `60000ms -> 82500 token`             |
| TTS        | `8 RMB / 万字符` `seed-icl-2.0` 口径     | `8.8 RMB / 万字符`        | `100 chars -> 88000 token`           |
| LLM_INPUT  | `0.2 RMB / 百万 tokens` `2.0-mini` 口径 | `0.22 RMB / 百万 tokens` | `1000 provider tokens -> 220 token`  |
| LLM_OUTPUT | `2 RMB / 百万 tokens` `2.0-mini` 口径   | `2.2 RMB / 百万 tokens`  | `1000 provider tokens -> 2200 token` |

说明：

- 上表基于 `1 RMB = 1,000,000 平台Token`
- 这是一组针对当前计费基线模型的推荐起始值，不是跨项目通用常量
- 实际线上价格以当前生效的 `billing.metering.rules` 为准
- 如果 LLM 模型切到 `lite / pro`，或 TTS 切到 `seed-tts-2.0`，必须单独新增或替换对应规则
- 如果拿到了实际采购账单，允许把 ASR 从公开刊例保守口径下调到真实成本口径，再重新生成 metering 规则
- `TTS` 规则建议显式带 `model`，不要只按 `provider` 复用价格
- 规则里的 `provider` / `model` 命名必须和上游入账时实际上传给 billing 的值保持一致

### 3.5 当前推荐配置示例

```yaml
billing:
  enabled: true
  metering:
    rules:
      - kind: ASR
        provider: DoubaoStreamASRProvider
        model: volc.bigasr.sauc.duration
        raw_unit: AUDIO_MS
        base_units: 60000
        token_amount: 82500

      - kind: LLM_INPUT
        provider: OpenAILLMProvider
        model: doubao-seed-2-0-mini-260428
        raw_unit: PROVIDER_TOKEN
        base_units: 1000
        token_amount: 220

      - kind: LLM_OUTPUT
        provider: OpenAILLMProvider
        model: doubao-seed-2-0-mini-260428
        raw_unit: PROVIDER_TOKEN
        base_units: 1000
        token_amount: 2200

      - kind: TTS
        provider: HuoshanStreamTTSProvider
        model: seed-icl-2.0
        raw_unit: TEXT_CHAR
        base_units: 100
        token_amount: 88000
```

### 3.6 官方参考与价格判断（2026-07-07）

下面的判断基于 `2026-07-07` 查阅的火山 / 豆包官方公开资料，以及当前项目给定的采购成本口径。

- 如果 `ASR 4.5 元/小时`、`LLM 2.0-mini 输入 0.2 / 输出 2 元 / 百万 tokens`、`TTS seed-icl-2.0 8 元/万字符`
  这三组值已经被采购侧或账单侧确认，那么按 10% 上浮生成 `4.95 / 8.8 / 0.22 / 2.2` 的平台售价是合理的。
- `ASR` 使用 `4.5 元/小时` 作为公开刊例保守口径是可以接受的；如果后续拿到更低的真实采购账单，可以再下调，不需要改 billing
  主链路。
- `LLM` 这里已经不再使用“一张统一 LLM 价表”，而是明确绑到 `doubao-seed-2-0-mini-260428`，这个方向是对的；后续如果切到
  `lite / pro / thinking`，必须单独建规则。
- `TTS` 这里的关键不是数学换算，而是口径一致：如果线上实际跑的是 `seed-icl-2.0`，就用这条规则；如果实际跑的是 `seed-tts-2.0`
  ，这条规则不能直接复用。
- billing 本身不校验 provider 价格对错，所以真正决定计费正确性的，是上游选择了哪条 `metering rule`，以及上游上报的
  `provider / model / raw_unit` 是否和规则完全一致。

官方参考链接：

- 方舟模型计费说明：`https://www.volcengine.com/docs/6581/2389072?lang=zh`
- RTC 接入 `resource_id` 映射：`https://www.volcengine.com/docs/6500/1588416`
- 豆包产品页：`https://www.volcengine.com/product/doubao`
- 语音处理产品页：`https://www.volcengine.com/products/Audio-editing-and-sound-processing`

## 运行路径

### 1. session/open

当前代码流程：

1. 校验 `device_did` 和认证设备是否一致
2. 先查 `session_id` 是否已存在
3. 若会话已存在，校验会话绑定设备并直接返回当前状态
4. 若会话不存在，则按 `(subject_type, subject_key)` 查找或创建 `u_bill_account`
5. 校验账户状态必须为 `ACTIVE`
6. 创建 `u_bill_session`

### 2. usage/debit

这是当前最重要的高频接口。

当前代码流程：

1. 先按 `usage_id` 查 `u_bill_txn`，命中则直接返回第一次结果
2. 若未命中，查询并锁住 `session + account`
3. 校验认证设备与会话设备一致
4. 直接使用请求里的 `usage_token`
5. 写入一条 `u_bill_txn(change_type=DEBIT)`
6. 更新 `u_bill_account.balance_token`
7. 如果余额扣穿，则把 `account/session` 标记为 `BLOCKED`
8. 如果没有扣穿，则只在活跃时间超过阈值时更新 `u_bill_session.last_activity_at`

几个关键点：

- 正常路径不再同步写第二张事实表
- 重复请求走 `usage_id` 幂等短路
- `should_stop` 来自 txn 里的 `session_status_after`
- 非幂等扣费只允许 `OPEN` 会话进入，`BLOCKED` 会话只能走幂等短路返回第一次成功结果

### 3. session/close

当前代码只做：

- 按 `session_id` 加锁查会话
- 校验设备身份
- 如果 `ended_at` 已经存在，直接返回
- 否则更新 `status / ended_at / last_activity_at`

## 并发与稳定性

当前设计优先保证正确性和稳定性，不对未压测前的具体 QPS 做承诺。

并发特征是：

- 幂等命中时，只需要按 `usage_id` 读一次流水
- 首次扣费时，只新增 1 条事实流水
- 同一 `account` / 同一 `session` 的扣费会通过行锁串行化
- 不同 `account` 之间天然分散，可通过设备分散度横向扩展

因此当前实现更适合：

- 主体以 `DEVICE` 为主
- 单设备单会话
- 大量分散设备并发写入

如果未来要支持“多个设备共享同一个账户并高频同时扣费”，再考虑预留额度或更复杂的账户并发模型，不放在当前版本内。

## 接口 DB 操作与耗时估算

### 统计口径

下面的次数和耗时只统计 billing 自身主链路：

- 只看 billing 三张表：`u_bill_account / u_bill_session / u_bill_txn`
- 不包含网关、序列化、日志输出等外围耗时
- 不包含设备鉴权的额外 DB 开销，当前 `DependsDeviceAuth` 本身不查库
- 不把事务的 `BEGIN / COMMIT` 以及嵌套事务 `SAVEPOINT` 单独算进“业务 DB 操作次数”

耗时是基于“同机房 MySQL、索引命中、无明显锁等待”的经验估算，不是压测结果。

### session/open

1. 会话已存在

- DB 操作：2 次
- 明细：
    - `select u_bill_session by session_id`
    - `select u_bill_account by account_id for update`
- 预估耗时：`3 ~ 10 ms`

2. 会话不存在，账户已存在

- DB 操作：3 次
- 明细：
    - `select u_bill_session by session_id`
    - `select u_bill_account by (subject_type, subject_key) for update`
    - `insert u_bill_session`
- 预估耗时：`5 ~ 12 ms`

3. 会话不存在，账户也不存在

- DB 操作：4 次
- 明细：
    - `select u_bill_session by session_id`
    - `select u_bill_account by (subject_type, subject_key) for update`
    - `insert u_bill_account`
    - `insert u_bill_session`
- 预估耗时：`6 ~ 15 ms`

补充说明：

- 并发竞争下，如果 `insert account` 或 `insert session` 触发唯一键冲突，代码会补一次查询，实际会多 `1` 次 DB 读取
- 这个接口不是高频热点，更多是会话建立时的准入接口

### usage/debit

1. 幂等命中

- DB 操作：1 次
- 明细：
    - `select u_bill_txn by usage_id`
- 预估耗时：`2 ~ 6 ms`

2. 首次扣费，且不需要更新 session

- DB 操作：4 次
- 明细：
    - `select u_bill_txn by usage_id`
    - `select u_bill_session join u_bill_account for update`
    - `insert u_bill_txn`
    - `update u_bill_account`
- 预估耗时：`6 ~ 15 ms`

3. 首次扣费，且需要更新 session

- DB 操作：5 次
- 明细：
    - `select u_bill_txn by usage_id`
    - `select u_bill_session join u_bill_account for update`
    - `insert u_bill_txn`
    - `update u_bill_account`
    - `update u_bill_session`
- 触发场景：
    - 余额扣穿，写入 `BLOCKED`
    - `last_activity_at` 达到刷新阈值
- 预估耗时：`8 ~ 20 ms`

补充说明：

- 当前高频路径的主要成本已经收敛到 `u_bill_txn` 单事实写入
- 真正影响尾延迟的核心不是 SQL 条数，而是“同一 `account/session` 上的锁竞争”
- 同一账户并发扣费会串行排队，所以热点账户的 P95 / P99 会明显高于分散设备场景

### session/close

1. 会话已经关闭

- DB 操作：1 次
- 明细：
    - `select u_bill_session by session_id for update`
- 预估耗时：`2 ~ 6 ms`

2. 正常关闭会话

- DB 操作：2 次
- 明细：
    - `select u_bill_session by session_id for update`
    - `update u_bill_session`
- 预估耗时：`4 ~ 10 ms`

### 评估结论

- 从 DB 操作数看，`usage/debit` 正常路径已经比较短，主路径是 `4 ~ 5` 次 billing SQL
- `session/open` 和 `session/close` 不是主要性能瓶颈
- 当前版本能否扛住并发，关键取决于同一账户的冲突比例，而不是接口名义上的平均 SQL 次数

## 幂等规则

- `usage_id` 必须全局唯一
- 重复调用同一个 `usage_id` 时，直接返回第一次成功入账的结果
- 当前 `charge_id` 直接等于 `usage_id`

## 当前文档口径

这份文档以当前代码为准，不描述尚未实现的充值、账单汇总或异步审计能力。  
上面的“定价策略”只描述上游 metering 配置口径，不表示 billing 热路径内置了价格计算。
