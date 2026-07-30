# x-mutual-pilot 方案设计

> 文档状态：已于 2026-07-30 完成单账号实现与本地验收。真实 X 读写仍须使用操作者凭据，并在上线前重新核验权限、计费与自动化政策。

## 1. 项目定位

`x-mutual-pilot` 是面向 X（原 Twitter）账号的互关关系与互动副驾驶。

它负责：

- 识别关注者、已关注者与互关用户；
- 发现互关用户的新帖子；
- 根据账号风格生成回复草稿；
- 识别新关注者并生成回关建议；
- 通过审批队列执行回复和回关；
- 记录每次判断、审批和写操作，支持追溯与停用。

默认工作模式是“自动发现与生成，人工确认后执行”，不是无人值守的批量互动机器人。

## 2. 目标与非目标

### 2.1 目标

1. 准确维护当前账号的关注、粉丝和互关集合。
2. 实时或准实时发现互关用户发布的新帖子。
3. 对值得互动的帖子生成符合账号语气的回复草稿。
4. 对新关注者进行可解释的回关评估。
5. 用最少权限调用 X 官方 API 完成获批操作。
6. 提供频率限制、去重、敏感内容过滤、审计和紧急停用。

### 2.2 非目标

- 不通过浏览器脚本、页面模拟点击或私有接口操作 X。
- 不批量、激进或无差别关注、取关、回复、点赞。
- 不把“关注了当前账号”视为同意接收自动回复。
- 不绕过 X API 的权限、配额、计费或风控限制。
- 不在未取得 X 明确许可时运行 AI 全自动回复机器人。
- 第一阶段不支持多账号矩阵、自动私信、自动点赞或自动取关。

## 3. 合规边界

实现时以 X 官方自动化规则为硬约束：

1. 所有读写操作必须通过 X 官方 API。
2. 互关关系本身不构成自动回复的用户许可。
3. 用户主动回复、提及账号或参与明确说明的互动活动，才可能构成回复意图。
4. AI 自动回复上线前需要取得 X 的书面明确批准。
5. 自动回关不得演变为批量、激进或无差别关注。
6. 每个用户交互最多自动回复一次，并提供退出机制。
7. 写操作必须经过内容安全、频率、去重和账号状态检查。

参考：

- X 自动化规则：https://help.x.com/en/rules-and-policies/x-automation
- X 官方 Skill：https://docs.x.com/tools/skill-md
- X API Follows：https://docs.x.com/x-api/users/follows/introduction
- X Activity：https://docs.x.com/x-api/activity/introduction
- X Manage Posts：https://docs.x.com/x-api/posts/manage-tweets/introduction

## 4. 推荐运行模式

### 4.1 Observe

只读取数据，不产生任何 X 写操作。

- 同步关注关系；
- 识别互关；
- 发现帖子；
- 输出回复草稿和回关建议；
- 用于验证 API、规则和模型质量。

### 4.2 Assisted（默认）

自动发现、评估和生成，人工审批后执行。

- 回复草稿进入审批队列；
- 回关建议进入审批队列；
- 审批通过后调用 API；
- 拒绝操作及原因同样写入审计日志。

### 4.3 Controlled Auto

仅在以下条件全部满足时开启：

- 已取得 X 对 AI 自动回复的书面批准；
- 用户通过回复、提及或明确活动规则表达了互动意图；
- 命中允许场景和白名单；
- 通过内容安全与敏感媒体检查；
- 未超过用户级、小时级和日级限额；
- 不是重复、模板化或低价值回复；
- 支持立即全局停用。

普通互关用户发布的新帖子不进入全自动回复模式。

## 5. 总体架构

```text
X API / X Activity / Filtered Stream
                 |
                 v
        Event Ingestion Layer
                 |
        +--------+---------+
        |                  |
        v                  v
Relationship Store   Post/Event Store
        |                  |
        +--------+---------+
                 v
      Policy & Risk Engine
                 |
        +--------+---------+
        |                  |
        v                  v
 Follow-back Scorer   Reply Draft Generator
        |                  |
        +--------+---------+
                 v
          Approval Queue
                 |
                 v
          X Action Executor
                 |
                 v
       Audit / Metrics / Alerts
```

## 6. 核心模块

### 6.1 X Adapter

统一封装 X 官方 API，避免业务逻辑直接拼接请求。

第一选择：

- X 官方 `xurl` CLI 与其 Skill；
- 安装 Skill：`npx skills add https://github.com/xdevplatform/xurl`。

主要能力：

- 获取当前账号；
- 获取 followers 与 following；
- 获取用户帖子或接入 Filtered Stream；
- 创建回复；
- 关注用户；
- 处理 OAuth、分页、配额和错误。

所有外部响应先转换为内部类型，再进入业务模块。

### 6.2 Relationship Sync

以稳定的 X `user_id` 作为关系主键，不以可变的用户名作为主键。

集合定义：

```text
followers = 关注当前账号的用户集合
following = 当前账号已关注的用户集合
mutuals   = followers ∩ following
```

更新方式：

- 优先使用 `follow.follow` / `follow.unfollow` 活动事件增量更新；
- 定时全量同步用于纠偏；
- 如果活动订阅不可用，使用分页拉取与本地快照差异识别新关注者；
- 用户改名时更新用户名，不改变 `user_id` 与历史记录。

### 6.3 Mutual Post Watcher

监听互关用户的新帖子。

优先方案：

- 使用 Filtered Stream 或 Filtered Stream Webhook；
- 按当前互关集合维护 `from:<handle>` 过滤规则；
- 关系变化后增量更新规则。

降级方案：

- 按最近活跃互关用户分批读取 User Posts Timeline；
- 保存 `since_id`，只处理新帖子；
- 严格限制轮询频率和读取字段。

进入候选队列前过滤：

- 转发、纯引用、广告和重复内容；
- 敏感媒体或敏感语言；
- 当前账号已经回复过的帖子；
- 已过互动时效的帖子；
- 低置信度语言或无法理解的内容；
- 黑名单、静默名单和明确退出用户。

### 6.4 Follow-back Scorer

新关注者不会被无条件自动回关，而是生成可解释建议。

建议评分维度：

- 是否与当前账号主题相关；
- 是否存在真实资料、正常发帖历史与合理互动；
- 是否疑似垃圾号、批量关注号或仿冒号；
- 是否命中允许名单、拒绝名单或组织域；
- 账号语言与目标受众是否匹配；
- 当前 following/follower 比例与当日操作额度。

输出：

```json
{
  "decision": "recommend_follow | review | reject",
  "score": 0,
  "reasons": [],
  "riskFlags": []
}
```

只有 `recommend_follow` 才进入快速审批队列；默认仍需人工确认。

### 6.5 Reply Draft Generator

输入：

- 原帖正文、语言、时间和公开上下文；
- 对话线程中必要的上文；
- 当前账号的语气配置；
- 回复目的：支持、补充、提问或致谢；
- 禁用话题、敏感词和长度限制。

输出：

- 一条首选草稿；
- 可选的一条更简洁草稿；
- 生成语言；
- 生成理由；
- 风险标签；
- 是否建议不回复。

硬性要求：

- 不捏造事实；
- 不伪装成人工实时阅读；
- 不复制模板或向多人发送近似内容；
- 不输出骚扰、歧视、成人、隐私或高风险建议；
- 不默认附带营销链接；
- 不为了互动率制造争议。

### 6.6 Policy & Risk Engine

所有候选操作在生成前和执行前各检查一次。

检查项：

- 运行模式是否允许该动作；
- 目标用户是否退出、拉黑或静默；
- 是否具备明确互动意图；
- 是否已经对该交互回复；
- 用户级冷却时间；
- 每小时、每日回复和关注上限；
- 内容敏感度；
- 原帖是否仍存在；
- 当前账号是否被限制；
- OAuth scope 是否满足；
- 是否处于全局暂停状态。

任一硬性规则失败时，禁止执行并记录原因。

### 6.7 Approval Queue

审批记录至少展示：

- 操作类型；
- 目标用户与原帖链接；
- 互关状态；
- 推荐理由和风险标签；
- 回复草稿或回关建议；
- 过期时间；
- approve、edit、reject、snooze 操作。

审批结果不可直接覆盖原草稿，修改前后内容都应保留。

### 6.8 Action Executor

只执行已批准且未过期的动作。

执行流程：

1. 获取幂等键并锁定任务；
2. 再次读取目标状态；
3. 再跑一次政策检查；
4. 调用 X API；
5. 保存响应 ID、时间和配额信息；
6. 对 429 执行退避，不立即重试；
7. 对 401/403 停止写操作并报警；
8. 不对不确定结果盲目重放。

## 7. 关键工作流

### 7.1 新关注者

```text
收到 inbound follow.follow
-> 写入关注事件
-> 检查是否已在 following
-> 若已关注，更新为 mutual
-> 若未关注，执行回关评分
-> 进入审批队列
-> 人工批准
-> 再检查关系与限额
-> Follow API
-> 更新 mutual 状态与审计日志
```

### 7.2 互关用户发帖

```text
收到新帖子
-> 验证作者仍为 mutual
-> 去重与基础过滤
-> 计算互动价值和风险
-> 生成回复草稿
-> 进入审批队列
-> 人工编辑或批准
-> 检查原帖仍存在
-> Create Post Reply API
-> 保存回复 ID 与审计记录
```

### 7.3 用户主动提及或回复

```text
收到 mention/reply
-> 判断是否表达回复意图
-> 检查退出状态和历史回复
-> 生成草稿
-> Assisted 模式进入审批队列
-> Controlled Auto 模式检查 X 批准状态及全部限制
-> 最多回复一次
-> 保存审计记录
```

## 8. 最小数据模型

### accounts

- `id`
- `x_user_id`
- `username`
- `mode`
- `writes_paused`
- `created_at`
- `updated_at`

### profiles

- `x_user_id`
- `username`
- `display_name`
- `bio`
- `language`
- `public_metrics`
- `last_seen_at`

### relationships

- `account_id`
- `target_user_id`
- `is_follower`
- `is_following`
- `is_mutual`
- `first_followed_at`
- `last_changed_at`

### posts

- `x_post_id`
- `author_user_id`
- `conversation_id`
- `text`
- `language`
- `created_at`
- `received_at`
- `raw_hash`

### action_candidates

- `id`
- `account_id`
- `action_type`
- `target_user_id`
- `target_post_id`
- `status`
- `score`
- `reasons`
- `risk_flags`
- `draft`
- `expires_at`
- `created_at`

### action_executions

- `id`
- `candidate_id`
- `idempotency_key`
- `approved_by`
- `approved_at`
- `request_summary`
- `x_result_id`
- `result_status`
- `error_code`
- `executed_at`

### opt_outs

- `account_id`
- `target_user_id`
- `scope`
- `reason`
- `created_at`

初期单账号版本可用 SQLite；需要多实例或多账号时再迁移到 PostgreSQL。

## 9. 配置与密钥

建议配置项：

```text
X_CLIENT_ID
X_CLIENT_SECRET
X_REDIRECT_URI
X_ACCOUNT_USERNAME
X_AGENT_MODE=observe|assisted|controlled-auto
X_WRITES_PAUSED=true
MAX_REPLIES_PER_HOUR
MAX_REPLIES_PER_DAY
MAX_FOLLOWS_PER_DAY
USER_REPLY_COOLDOWN_HOURS
APPROVAL_EXPIRY_MINUTES
```

要求：

- 密钥只放环境变量或专用秘密管理器；
- 不提交 `.env`；
- 日志不记录 token、完整授权头或私信内容；
- 使用专用 X Developer App；
- OAuth scope 采用最小权限；
- 默认 `X_WRITES_PAUSED=true`。

## 10. 可靠性与可观测性

必须记录：

- 事件接收数、去重数和失败数；
- 当前 followers、following、mutuals 数量；
- 草稿生成数、批准率、拒绝率和编辑率；
- 回复、关注成功率；
- 401、403、429 和 5xx 数量；
- API 用量与预计成本；
- 队列积压与最老任务年龄；
- 全局暂停与恢复操作。

告警条件：

- OAuth 失效；
- 连续 403 或账号受限；
- 429 明显增加；
- 写操作数量异常；
- 重复回复检测命中；
- Webhook CRC 失败；
- 事件超过预期时间未到达。

## 11. 测试策略

### 11.1 单元测试

- followers 与 following 交集；
- 关系事件顺序错乱与重复事件；
- 新关注者评分规则；
- 回复资格和 opt-out 判断；
- 用户级、小时级、日级限额；
- 幂等键与重复执行保护；
- 敏感内容与黑名单过滤。

### 11.2 契约测试

- X API 响应转换；
- 分页；
- 401、403、429、5xx；
- Webhook CRC；
- follow、unfollow 和 post 事件载荷；
- Create Post 与 Follow 请求字段。

### 11.3 集成测试

- Observe 模式禁止全部写操作；
- 未审批任务不可执行；
- 过期审批不可执行；
- 原帖删除后不可回复；
- 关系变化后不再把作者视为 mutual；
- 执行结果不确定时不重复写入。

### 11.4 人工验收

- 用测试账号完成 OAuth；
- 新关注事件能进入回关建议队列；
- 互关账号的新帖子能生成草稿；
- 编辑、批准、拒绝和暂停有效；
- X 上实际结果与审计记录一致；
- 紧急停用后不再产生写操作。

## 12. 分阶段实施

当前进度（2026-07-30）：Phase 1–4 的单账号代码路径均已落地，包括
SQLite、增量发现、评分、草稿、审批、审计、受控执行、Controlled Auto
门禁和本地控制台。离线测试与浏览器验收已通过；真实 X 读写仍需操作者凭据、
API 额度及 AI 自动回复书面许可，不能由仓库测试替代。

### Phase 0：接入确认

- 创建独立 X Developer App；
- 确认可用 API、计费、scope 和活动事件权限；
- 确认是否申请 AI 自动回复书面批准；
- 安装并验证官方 `xurl` Skill。

交付标准：能读取当前账号、followers、following 和一条公开帖子，不执行写操作。

### Phase 1：只读 MVP

- 建立关系快照；
- 计算 mutuals；
- 接入新关注事件或快照差异；
- 发现互关用户的新帖子；
- 保存候选事件。

交付标准：Observe 模式稳定运行，零写操作。

### Phase 2：草稿与审批

- 增加回关评分；
- 增加回复草稿生成；
- 增加审批队列；
- 增加审计与全局暂停。

交付标准：能完整演示候选产生、编辑、批准和拒绝，但执行器仍为 dry-run。

### Phase 3：受控写操作

- 启用批准后的回复；
- 启用批准后的回关；
- 增加幂等、退避、限额和告警；
- 用测试账号小流量验证。

交付标准：每个写操作都有审批人与可追溯记录，无重复执行。

### Phase 4：有限自动化

- 仅在获得 X 许可后实施；
- 仅覆盖主动提及、主动回复或明确 opt-in 场景；
- 设置极低日限额；
- 保留实时监控和一键停用。

交付标准：满足政策、质量和风险门槛后再逐步放量。

## 13. 验收标准

1. 能正确识别 followers、following 与 mutuals。
2. 能识别新关注者，不重复创建候选。
3. 能发现互关用户新帖子并生成可编辑草稿。
4. 默认模式下没有人工审批就不会产生任何写操作。
5. 普通互关帖子不会触发全自动回复。
6. 回关操作经过评分、限额与审批。
7. 所有写操作具备幂等、审计和失败保护。
8. 401、403、429 能停止或延迟执行，不会快速重试。
9. 全局暂停能够立即阻止新写操作。
10. 不使用网页脚本、私有接口或明文密钥。

## 14. Skill 目录

当前实现结构：

```text
x-mutual-pilot/
├── README.md
├── SKILL.md
├── agents/
│   └── openai.yaml
├── docs/
│   ├── 00-feature-map.md
│   ├── 01-page-route-map.md
│   ├── 02-api-map.md
│   ├── 03-data-model-map.md
│   ├── 04-test-map.md
│   ├── 05-release-checklist.md
│   └── 06-solution-design.md
├── references/
│   ├── x-api.md
│   ├── automation-policy.md
│   └── decision-rules.md
├── scripts/
│   └── x_mutual_pilot.py
├── src/
│   └── x_mutual_pilot/
└── tests/
```

实现时保持 `SKILL.md` 简洁，将 API、政策和评分细则放入 `references/`，将可重复且需要确定性的操作放入 `scripts/`。
