# Test Map

No test framework or test files exist yet.

| Area | Minimum coverage | Test level |
|---|---|---|
| Relationships | Set intersection, duplicate/out-of-order events | Unit |
| Follow-back scoring | Allow, review, reject, and risk explanations | Unit |
| Policy engine | Opt-out, consent, cooldown, hourly/daily limits | Unit |
| Executor | Approval, expiry, idempotency, uncertain results | Unit / integration |
| X adapter | Payload mapping, pagination, 401/403/429/5xx, webhook CRC | Contract |
| Operating modes | Observe blocks writes; Assisted requires approval | Integration |
| Post lifecycle | Deleted post, changed relationship, duplicate reply | Integration |

Automated tests must use fixtures or a fake adapter and must never write to a live
X account. Manual acceptance with a dedicated test account belongs to the release
checklist.
