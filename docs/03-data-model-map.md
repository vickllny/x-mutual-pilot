# Data Model Map

SQLite persistence is implemented in `src/x_mutual_pilot/store.py`. Stable X IDs
are primary identifiers; usernames remain mutable attributes.

| Model | Purpose | Key lifecycle |
|---|---|---|
| `accounts` | Mode, X approval flag, persistent write pause | Owns all account state |
| `profiles` | Cached public profile data and metrics | Upserted by `x_user_id` |
| `relationships` | Follower, following, and mutual state | Full-sync diff with baseline protection |
| `posts` | Source posts and SHA-256 deduplication hashes | Insert-once discovery record |
| `action_candidates` | Score, risks, drafts, approval, snooze, expiry | Unique dedupe key |
| `action_executions` | Idempotency key, result ID/status, error code | One row per candidate |
| `opt_outs` | Exclusions by `all`, `reply`, or `follow` | Checked before discovery and execution |
| `audit_log` | Candidate, pause, and execution events | Append-only |
| `cursors` | Baseline marker and timeline `since_id` values | Updated after processing |

## Exported Snapshot

`src/x_mutual_pilot/relationships.py` also emits schema version 1 with the
account ID, UTC timestamp, counts, deduplicated profiles, mutuals, and secret-free
runtime metadata.

The database defaults to `data/x-mutual-pilot.sqlite3` and is ignored by Git.
PostgreSQL remains deferred until multi-instance requirements exist.
