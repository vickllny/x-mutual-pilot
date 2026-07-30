# Release Checklist

The single-account implementation is feature-complete locally but has not been
verified with operator-owned live X credentials.

## Before Live Use

- Revalidate X API pricing, scopes, quotas, self-serve reply restrictions, and automation policy.
- Use a dedicated X Developer App and test account.
- Keep secrets outside the repository and logs.
- Start in `observe`; keep `X_WRITES_PAUSED=true`.
- Obtain written X approval before enabling AI auto-replies.

## Verification

- Run `PYTHONPATH=src python3 -m unittest discover -s tests -v`.
- Run `python3 -m compileall -q src scripts tests`.
- Run `python3 scripts/x_mutual_pilot.py doctor`.
- Verify the loopback dashboard at desktop and mobile widths.
- Confirm Observe mode produces zero writes.
- Confirm unapproved, expired, duplicate, opted-out, and no-intent actions fail.
- Confirm 401/403 persistently pause writes and 429 is not blindly retried.
- Confirm resume and manual execution require explicit confirmation flags.
- Confirm every decision and attempt has an audit record.

## Controlled Live Check

- Verify a read-only relationship sync first.
- Verify one approved follow and one explicit-mention reply with minimal limits.
- Confirm the X result matches the stored execution record.
- Confirm AI replies set `made_with_ai`.
- Enable Controlled Auto only after Assisted-mode acceptance passes.
