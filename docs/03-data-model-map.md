# Data Model Map

Stable X IDs are primary identifiers; usernames are mutable attributes. The
read-only MVP implements a JSON relationship snapshot; persistent models remain
proposed.

| Model | Purpose | Key relationships / lifecycle |
|---|---|---|
| `accounts` | Managed account, operating mode, global write pause | Owns relationships and candidates |
| `profiles` | Cached public X profile data | Updated without changing `x_user_id` |
| `relationships` | Follower, following, and mutual state | Incremental events plus full-sync correction |
| `posts` | Candidate source posts and deduplication hashes | Retained for context and audit |
| `action_candidates` | Scores, reasons, risks, drafts, approval state | Expires before execution |
| `action_executions` | Idempotent write attempt and result | Immutable audit trail |
| `opt_outs` | User-level exclusions | Checked before generation and execution |

## Implemented Snapshot

`src/x_mutual_pilot/relationships.py` emits schema version 1 with:

- `account_user_id`, UTC `generated_at`, and follower/following/mutual counts;
- deduplicated follower and following profile arrays;
- a mutual profile array derived from the intersection of stable user IDs;
- runtime metadata added by the CLI, without credentials.

SQLite is proposed for the initial single-account version; PostgreSQL is deferred
until multi-instance or multi-account requirements exist. See
`docs/06-solution-design.md` §8 for planned fields.
