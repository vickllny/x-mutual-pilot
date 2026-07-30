# x-mutual-pilot

[English](README.md) | [简体中文](README.zh-CN.md)

面向 X（原 Twitter）账号的互关关系与互动副驾驶。项目坚持“自动发现、人工确认、受控执行”，不做网页脚本、批量互动或未经许可的 AI 自动回复。

## 已实现功能

当前实现包括：

- 分页同步 followers/following，并按稳定 X User ID 识别互关；
- 用 SQLite 保存关系、游标、退出记录、候选、执行和审计；
- 对新关注者进行可解释评分并生成去重后的回关建议；
- 轮询互关帖子和明确提及；
- 本地安全草稿或可选 OpenAI Responses API 草稿；
- 审批、编辑、拒绝、稍后处理、过期、限额和幂等；
- 执行前重新检查原帖，并支持紧急暂停；
- 只绑定本机回环地址的响应式审批控制台；
- 仅面向明确提及场景、具备完整门禁的 Controlled Auto 模式。

## 快速开始

需要 Python 3.10+，无第三方运行时依赖。先在 X Developer Console 创建专用 App，并从 Observe 模式开始：

```bash
export X_BEARER_TOKEN="..."
export X_ACCOUNT_USER_ID="123456789"
export X_AGENT_MODE="observe"
export X_WRITES_PAUSED="true"

python3 scripts/x_mutual_pilot.py doctor
python3 scripts/x_mutual_pilot.py init-db
python3 scripts/x_mutual_pilot.py sync-relationships
python3 scripts/x_mutual_pilot.py poll-posts
python3 scripts/x_mutual_pilot.py status
```

启动本地审批控制台：

```bash
python3 scripts/x_mutual_pilot.py serve
```

访问 `http://127.0.0.1:8765`。控制台支持审批、编辑、拒绝、稍后处理和暂停。恢复写操作必须使用 CLI 明确确认：

```bash
export X_WRITES_PAUSED="false"
python3 scripts/x_mutual_pilot.py resume --actor owner --confirm-resume
```

## 人工辅助写操作

写操作需要 OAuth 用户访问令牌、有效审批和全部策略检查：

```bash
export X_USER_ACCESS_TOKEN="..."
export X_AGENT_MODE="assisted"
export X_WRITES_PAUSED="false"

python3 scripts/x_mutual_pilot.py approve CANDIDATE_ID --actor reviewer
python3 scripts/x_mutual_pilot.py execute CANDIDATE_ID \
  --actor operator --confirm-live-write
```

设置 `OPENAI_API_KEY` 可启用 AI 草稿，默认模型为
`OPENAI_MODEL=gpt-5.6-luna`，请求使用 `store: false`。除非设置
`X_AI_REPLY_APPROVED=true`，AI 回复始终禁止执行。

Controlled Auto 还必须同时满足：

```bash
export X_AGENT_MODE="controlled-auto"
export X_CONTROLLED_AUTO_ENABLED="true"
export X_AI_REPLY_APPROVED="true"
export X_WRITES_PAUSED="false"
python3 scripts/x_mutual_pilot.py run-cycle
```

该模式只会自动审批和执行明确提及当前账号的回复。普通互关帖子仍不可执行，因为关注关系不构成回复许可。

## 测试

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

测试使用伪造 HTTP 响应，不访问真实 X 账号。

## 项目结构

```text
agents/       Skill 的 UI 元数据
docs/         功能、API、模型、测试、发布索引与方案设计
references/   X API 与自动化政策边界
scripts/      可直接调用的 CLI 入口
src/          API、策略、持久化、服务、CLI 和控制台
tests/        离线单元、契约和集成测试
SKILL.md      Codex Skill 入口
```

## 安全边界

- 默认 `X_AGENT_MODE=observe`、`X_WRITES_PAUSED=true`。
- 不提交 `.env`、token 或关系快照。
- 401、403、429 或结果不确定的写操作不会自动重试。
- X 返回 401 或 403 后持久化暂停全部写操作。
- 自动回复前必须满足用户意图与退出机制要求；AI 自动回复还需取得 X 的书面明确批准。
- 管理控制台只绑定回环地址，所有状态变更均校验 CSRF。

启用真实写操作前重新核验 [X API 文档](https://docs.x.com/x-api/overview) 与 [X 自动化规则](https://help.x.com/en/rules-and-policies/x-automation)。真实 API 验收需要操作者自己的 X 凭据和许可；自动化测试不会访问 X 或 OpenAI。
