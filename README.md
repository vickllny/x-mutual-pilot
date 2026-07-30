# x-mutual-pilot

[English](README.md) | [简体中文](README.zh-CN.md)

A mutual-relationship and interaction copilot for X (formerly Twitter). The
project follows an “automated discovery, human approval, controlled execution”
model. It does not automate the X website, perform bulk engagement, or send
unapproved AI-generated replies.

## Current status

The first read-only MVP can:

- validate the operating mode, global write pause, and read-only credentials;
- paginate through followers and following with X API v2;
- calculate mutuals using stable X user IDs;
- emit a secret-free JSON relationship snapshot;
- test configuration, pagination, errors, deduplication, and set operations offline.

This version cannot reply, follow, unfollow, or perform any other X write action.

## Quick start

Python 3.10+ is required. There are no third-party runtime dependencies. Create
a dedicated App in the X Developer Console and obtain a read-only Bearer Token.

```bash
export X_BEARER_TOKEN="..."
export X_ACCOUNT_USER_ID="123456789"
export X_AGENT_MODE="observe"
export X_WRITES_PAUSED="true"

python3 scripts/x_mutual_pilot.py doctor
python3 scripts/x_mutual_pilot.py sync-relationships \
  --output data/relationships.json
```

`doctor` reports configuration readiness without printing the token.
`sync-relationships` calls only:

- `GET /2/users/:id/followers`
- `GET /2/users/:id/following`

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
src/          Read-only adapter, configuration, and domain logic
tests/        Offline unit and contract tests
SKILL.md      Codex Skill entry point
```

## Safety boundaries

- Default to `X_AGENT_MODE=observe` and `X_WRITES_PAUSED=true`.
- Never commit `.env` files, tokens, or relationship snapshots.
- Do not automatically retry 401, 403, or 429 responses.
- Require clear user intent and an opt-out mechanism before automated replies.
- Obtain X’s prior written and explicit approval before operating an AI reply bot.

Recheck the [X API documentation](https://docs.x.com/x-api/overview) and
[X automation rules](https://help.x.com/en/rules-and-policies/x-automation)
before implementing write actions.
