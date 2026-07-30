# Release Checklist

The project has a local read-only MVP but has not been verified with live X
credentials.

## Before Any Implementation Release

- Revalidate official X API availability, pricing, scopes, quotas, and automation policy.
- Use a dedicated X Developer App and test account.
- Keep secrets outside the repository and logs.
- Default to `observe` or `assisted`; keep `X_WRITES_PAUSED=true`.

## Verification

- Run `PYTHONPATH=src python3 -m unittest discover -s tests -v`.
- Run `python3 scripts/x_mutual_pilot.py doctor` with a dedicated test App.
- Confirm relationship sync uses only the two documented GET endpoints.
- Run the smallest relevant unit, contract, and integration tests from `docs/04-test-map.md`.
- Confirm Observe mode produces zero write calls.
- Confirm unapproved, expired, duplicate, and policy-rejected actions cannot execute.
- Verify 401/403 stop writes and 429 applies backoff.
- Confirm every decision and write attempt has an audit record.

## Controlled Live Check

- Obtain any required written approval before enabling AI auto-replies.
- Start with a dedicated test account and minimal daily limits.
- Verify the emergency write pause before the first live write.
- Compare the X result with the stored execution record.

Record exact commands and environment-specific steps after the implementation
stack is selected.
