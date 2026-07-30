# X Automation Safety Boundary

Reviewed against X's official automation rules on 2026-07-30. Revalidate before
enabling any write behavior.

## Hard constraints

- Use the official X API; never automate the website or private endpoints.
- Do not treat following an account as consent to receive an automated reply.
- Require clear user intent, an easy opt-out, and at most one automated response
  per user interaction.
- Obtain X's prior written and explicit approval before operating an AI-powered
  automated reply bot.
- Avoid aggressive, indiscriminate, duplicate, or unsolicited interactions.
- Check content safety and confirm the source post still exists before replying.

## Project defaults

- Run in `observe` mode.
- Keep all writes paused.
- Require human approval for Assisted replies and follow-back actions.
- Allow Controlled Auto only for explicit mentions when the dedicated enable
  flag and written X approval flag are both present.
- Recheck policy, source post, expiry, quotas, cooldown, opt-out, and idempotency
  immediately before execution.
- Stop writes on authentication, authorization, account restriction, or
  rate-limit failures.
- Persistently pause writes after 401 or 403 and never blindly replay an
  uncertain write.

Official reference:

- https://help.x.com/en/rules-and-policies/x-automation
