---
name: x-mutual-pilot
description: Safely operate an X mutual-relationship and interaction copilot with relationship sync, post and mention discovery, follow-back scoring, reply drafts, approval queues, audit, and gated execution. Use when Codex needs to inspect X relationships, create or review action candidates, run the loopback approval console, enforce X automation policy, or execute an explicitly approved X action.
---

# X Mutual Pilot

Default to Observe mode. Perform a live write only after the user explicitly
requests it and every runtime gate passes.

## Run the workflow

1. Read `references/automation-policy.md` before proposing any write behavior.
2. Read `references/x-api.md` before changing API calls or fields.
3. Read `references/decision-rules.md` before changing scoring or policy.
4. Require `X_BEARER_TOKEN` and a numeric `X_ACCOUNT_USER_ID`.
5. Run the configuration check and initialize state:

   ```bash
   python3 scripts/x_mutual_pilot.py doctor
   python3 scripts/x_mutual_pilot.py init-db
   ```

6. Discover candidates:

   ```bash
   python3 scripts/x_mutual_pilot.py sync-relationships
   python3 scripts/x_mutual_pilot.py poll-posts
   python3 scripts/x_mutual_pilot.py list-candidates --status pending
   ```

7. Review through CLI or `python3 scripts/x_mutual_pilot.py serve`.
8. Require `--confirm-live-write` for manual execution.
9. Report counts and failures without exposing tokens or authorization headers.

## Preserve safety

- Keep `X_AGENT_MODE=observe` and `X_WRITES_PAUSED=true` by default.
- Use only official X API endpoints; never script the X website.
- Treat a follow as a relationship signal, not consent to receive automated replies.
- Keep AI replies blocked unless X's written approval is represented by
  `X_AI_REPLY_APPROVED=true`.
- Require explicit mention intent for API replies.
- Preserve approval, expiry, policy rechecks, limits, idempotency, audit, and the
  emergency pause.
- Stop on authentication, permission, or rate-limit errors; do not blindly retry.
- Bind the dashboard only to loopback. Resume writes only through the confirmed
  CLI command.

## Validate changes

Run:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Keep tests offline and use fake transports for X API behavior.
