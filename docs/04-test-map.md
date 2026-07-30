# Test Map

Tests use Python's standard-library `unittest` and fake HTTP responses.

| Area | Coverage | Test file |
|---|---|---|
| Configuration | Safe defaults, controlled-auto gates, secret-safe diagnostics | `tests/test_config.py` |
| Drafts | Local language fallback and OpenAI response parsing | `tests/test_drafts.py` |
| Relationships | Set intersection, duplicate profiles, invalid IDs | `tests/test_relationships.py` |
| Content safety | Sensitive terms, configured blocks, possible personal data | `tests/test_safety.py` |
| Persistence | Baseline diff, candidates, approval, pause, opt-out, snooze | `tests/test_store.py` |
| Follow scoring | Recommend/reject and risk explanations | `tests/test_scoring.py` |
| Policy | Consent, pauses, expiry, opt-out, cooldown, limits | `tests/test_policy.py` |
| Executor | Approval, idempotency, no-intent block, auth-failure pause | `tests/test_executor.py` |
| X adapter | Pagination, read/write payloads, 429 safety, token-loop guard | `tests/test_x_api.py` |
| Services | New followers, posts, mentions, Controlled Auto approval | `tests/test_services.py` |
| Dashboard | Metrics, queue controls, CSRF guard | `tests/test_web.py` |

Automated tests never write to live X or call OpenAI.

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```
