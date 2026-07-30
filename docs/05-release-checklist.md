# Release Checklist

The project has no releasable implementation yet. Apply this checklist as phases
are delivered.

## Before Any Implementation Release

- Revalidate official X API availability, pricing, scopes, quotas, and automation policy.
- Use a dedicated X Developer App and test account.
- Keep secrets outside the repository and logs.
- Default to `observe` or `assisted`; keep `X_WRITES_PAUSED=true`.

## Verification

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
