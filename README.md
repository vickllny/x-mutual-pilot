# x-mutual-pilot

[English](README.md) | [简体中文](README.zh-CN.md)

A mutual-relationship and interaction copilot for X (formerly Twitter). The
project follows an “automated discovery, human approval, controlled execution”
model. It does not automate the X website, perform bulk engagement, or send
unapproved AI-generated replies.

## Features

The implementation includes:

- paginated follower/following sync and mutual detection by stable X user ID;
- SQLite snapshots, cursors, opt-outs, candidates, executions, and audit history;
- explainable new-follower scoring and deduplicated follow-back suggestions;
- mutual-post polling plus explicit mention discovery;
- local reply drafts or optional OpenAI Responses API drafts;
- approval, editing, rejection, snooze, expiry, rate limits, and idempotency;
- approved follow/reply execution with post revalidation and emergency pause;
- a responsive, loopback-only approval console;
- a fully gated Controlled Auto mode for explicit mentions only.

## Quick start

Python 3.10+ is required, with no third-party runtime dependencies. Create a
dedicated App in the X Developer Console and start in Observe mode:

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

Run the approval console locally:

```bash
python3 scripts/x_mutual_pilot.py serve
```

Open `http://127.0.0.1:8765`. The console can approve, edit, reject, snooze, and
pause. Resume requires the explicit CLI confirmation:

```bash
export X_WRITES_PAUSED="false"
python3 scripts/x_mutual_pilot.py resume --actor owner --confirm-resume
```

## Assisted writes

Writes require an OAuth user access token, an approved unexpired candidate, and
all policy gates:

```bash
export X_USER_ACCESS_TOKEN="..."
export X_AGENT_MODE="assisted"
export X_WRITES_PAUSED="false"

python3 scripts/x_mutual_pilot.py approve CANDIDATE_ID --actor reviewer
python3 scripts/x_mutual_pilot.py execute CANDIDATE_ID \
  --actor operator --confirm-live-write
```

Optional AI drafts use `OPENAI_API_KEY` and default to
`OPENAI_MODEL=gpt-5.6-luna`. They are sent with `store: false`. AI replies remain
blocked unless `X_AI_REPLY_APPROVED=true`.

Controlled Auto additionally requires all of:

```bash
export X_AGENT_MODE="controlled-auto"
export X_CONTROLLED_AUTO_ENABLED="true"
export X_AI_REPLY_APPROVED="true"
export X_WRITES_PAUSED="false"
python3 scripts/x_mutual_pilot.py run-cycle
```

This mode only auto-approves and executes replies to explicit mentions. Ordinary
mutual posts remain non-executable because a follow is not reply consent.

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Tests use fake HTTP responses and never access a live X account.

## Project structure

```text
agents/       Skill UI metadata
docs/         Feature, API, model, test, release, and design documents
references/   X API and automation-policy boundaries
scripts/      Directly executable CLI entry point
src/          API, policy, persistence, services, CLI, and dashboard
tests/        Offline unit, contract, and integration tests
SKILL.md      Codex Skill entry point
```

## Safety boundaries

- Default to `X_AGENT_MODE=observe` and `X_WRITES_PAUSED=true`.
- Never commit `.env` files, tokens, or relationship snapshots.
- Never automatically retry 401, 403, 429, or uncertain writes.
- Persistently pause writes after X returns 401 or 403.
- Require clear user intent and an opt-out mechanism before automated replies.
- Obtain X’s prior written and explicit approval before operating an AI reply bot.
- Bind the management console to loopback only and protect mutations with CSRF.

Recheck the [X API documentation](https://docs.x.com/x-api/overview) and
[X automation rules](https://help.x.com/en/rules-and-policies/x-automation)
before enabling live writes. Live API acceptance requires the operator’s own X
credentials and approval; automated tests never contact X or OpenAI.
