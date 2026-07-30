# Test Map

Tests use Python's standard-library `unittest` and fake HTTP responses.

| Area | Minimum coverage | Test file / planned level |
|---|---|---|
| Configuration | Safe defaults, invalid IDs/modes, secret-safe diagnostics | `tests/test_config.py` |
| Relationships | Set intersection, duplicate profiles, invalid IDs | `tests/test_relationships.py` |
| Follow-back scoring | Allow, review, reject, and risk explanations | Unit |
| Policy engine | Opt-out, consent, cooldown, hourly/daily limits | Unit |
| Executor | Approval, expiry, idempotency, uncertain results | Unit / integration |
| X adapter | Pagination, authorization header, 429 safety, token-loop guard | `tests/test_x_api.py` |
| Operating modes | Observe blocks writes; Assisted requires approval | Integration |
| Post lifecycle | Deleted post, changed relationship, duplicate reply | Integration |

Automated tests must use fixtures or a fake adapter and must never write to a live
X account. Manual acceptance with a dedicated test account belongs to the release
checklist.

Run all current tests:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```
