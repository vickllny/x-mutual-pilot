---
name: x-mutual-pilot
description: Safely inspect an X account's followers, following, and mutual relationships and prepare policy-aware interaction workflows. Use when Codex needs to validate X account automation configuration, produce a read-only relationship snapshot, assess proposed follow-back or reply workflows, or enforce X automation safety boundaries.
---

# X Mutual Pilot

Operate in read-only mode unless the user explicitly requests a later implemented
workflow and all approval gates exist.

## Inspect relationships

1. Read `references/automation-policy.md` before proposing any write behavior.
2. Read `references/x-api.md` before changing API calls or fields.
3. Require `X_BEARER_TOKEN` and a numeric `X_ACCOUNT_USER_ID`.
4. Run the configuration check:

   ```bash
   python3 scripts/x_mutual_pilot.py doctor
   ```

5. Produce a relationship snapshot:

   ```bash
   python3 scripts/x_mutual_pilot.py sync-relationships \
     --output data/relationships.json
   ```

6. Report counts and failures without exposing tokens or authorization headers.

## Preserve safety

- Keep `X_AGENT_MODE=observe` and `X_WRITES_PAUSED=true` by default.
- Use only official X API endpoints; never script the X website.
- Treat a follow as a relationship signal, not consent to receive automated replies.
- Do not add a write path without approval, policy rechecks, limits, idempotency,
  audit records, and an emergency pause.
- Stop on authentication, permission, or rate-limit errors; do not blindly retry.

## Validate changes

Run:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Keep tests offline and use fake transports for X API behavior.
