# Feature Map

All planned single-account workflows are implemented. Live X acceptance remains
operator-gated because credentials and written approval are external.

| Module | Feature | Status | Main files | Tests |
|---|---|---|---|---|
| X Adapter | Read relationships/timelines; revalidate posts; follow and reply | Implemented, live-gated | `src/x_mutual_pilot/x_api.py` | `tests/test_x_api.py` |
| Relationships | Persist snapshots, detect changes, calculate mutuals | Implemented | `store.py`, `relationships.py` | `test_store.py`, `test_relationships.py` |
| Post Watcher | Poll mutual posts and explicit mentions with cursors and filters | Implemented | `src/x_mutual_pilot/services.py` | `tests/test_services.py` |
| Follow-back | Explainably score new followers | Implemented | `src/x_mutual_pilot/scoring.py` | `tests/test_scoring.py` |
| Reply Drafts | Generate local or optional OpenAI Responses API drafts | Implemented | `src/x_mutual_pilot/drafts.py` | `tests/test_drafts.py` |
| Policy & Risk | Enforce consent, opt-outs, pauses, expiry, cooldown, and limits | Implemented | `src/x_mutual_pilot/policy.py` | `tests/test_policy.py` |
| Approval & Execution | Approve, edit, reject, snooze, and idempotently execute | Implemented, live-gated | `store.py`, `executor.py`, `cli.py` | `test_executor.py`, `test_store.py` |
| Audit & Console | Persist audit events, metrics, pause state, and review UI | Implemented | `store.py`, `web.py` | `tests/test_web.py` |

Update only affected rows when implementation status or source locations change.
