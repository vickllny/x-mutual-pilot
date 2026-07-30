# Decision Rules

## Follow-back scoring

Start from a neutral review score, then add explainable signals for a complete
profile, verification, established activity, audience, and account-topic match.
Subtract for an empty profile, very limited activity, protected status, or a
bulk-following pattern.

- `65–100`: `recommend_follow`
- `40–64`: `review`
- `0–39` or bulk-following risk: `reject`

Only non-rejected results enter the approval queue. The initial relationship
snapshot is a baseline and never creates follow candidates for every historical
follower.

## Reply eligibility

- Mutual posts may create drafts for review but carry `no_explicit_intent` and
  cannot execute through the API.
- Direct mentions create explicit-intent candidates.
- Sensitive, empty, duplicate, self-authored, or opted-out posts are skipped.
- AI drafts carry `ai_generated`; execution requires the X approval flag.

## Execution gates

Require all of:

- approved and unexpired candidate;
- non-Observe mode and both pause gates disabled;
- no opt-out, duplicate execution, cooldown, or exceeded limit;
- explicit intent for replies;
- X written approval flag for AI replies;
- source post still available;
- an OAuth user token and explicit manual write confirmation, unless the
  separately enabled Controlled Auto path applies.

Never automatically retry an uncertain write result.
