# x-mutual-pilot

[English](README.md) | [简体中文](README.zh-CN.md)

面向 X（原 Twitter）账号的互关关系与互动副驾驶。项目坚持“自动发现、人工确认、受控执行”，不做网页脚本、批量互动或未经许可的 AI 自动回复。

## 当前状态

首个只读 MVP 已实现：

- 校验运行模式、写操作暂停状态和 X API 只读凭据；
- 通过 X API v2 分页读取 followers 与 following；
- 以稳定的 X `user_id` 计算互关集合；
- 输出不含密钥的 JSON 关系快照；
- 用离线测试覆盖配置、分页、错误处理、去重和集合计算。

当前版本没有回复、关注、取关或其他 X 写操作。

## 快速开始

需要 Python 3.10+，无第三方运行时依赖。先在 X Developer Console 创建专用 App，并准备只读 Bearer Token。

```bash
export X_BEARER_TOKEN="..."
export X_ACCOUNT_USER_ID="123456789"
export X_AGENT_MODE="observe"
export X_WRITES_PAUSED="true"

python3 scripts/x_mutual_pilot.py doctor
python3 scripts/x_mutual_pilot.py sync-relationships \
  --output data/relationships.json
```

`doctor` 只报告配置是否就绪，不显示 token。`sync-relationships` 只调用：

- `GET /2/users/:id/followers`
- `GET /2/users/:id/following`

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
src/          只读适配器、配置与领域逻辑
tests/        离线单元和契约测试
SKILL.md      Codex Skill 入口
```

## 安全边界

- 默认 `X_AGENT_MODE=observe`、`X_WRITES_PAUSED=true`。
- 不提交 `.env`、token 或关系快照。
- 401/403/429 不自动重试；调用失败时停止并返回安全错误。
- 自动回复前必须满足用户意图与退出机制要求；AI 自动回复还需取得 X 的书面明确批准。

实施写操作前重新核验 [X API 文档](https://docs.x.com/x-api/overview) 与 [X 自动化规则](https://help.x.com/en/rules-and-policies/x-automation)。
