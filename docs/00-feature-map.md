# Feature Map

The repository now includes a read-only relationship MVP. Write workflows remain
design-only.

| Module | Planned feature | Status | Main reference | Planned tests |
|---|---|---|---|---|
| X Adapter | Read followers/following with pagination and safe HTTP errors | Read-only MVP | `src/x_mutual_pilot/x_api.py`, `scripts/x_mutual_pilot.py` | `tests/test_x_api.py` |
| Relationships | Deduplicate profiles and calculate mutuals by X user ID | Read-only MVP | `src/x_mutual_pilot/relationships.py` | `tests/test_relationships.py` |
| Post Watcher | Discover and filter new posts from mutuals | Designed | `docs/06-solution-design.md` §6.3 | Unit and integration tests |
| Follow-back | Score new followers and explain recommendations | Designed | `docs/06-solution-design.md` §6.4 | Unit tests |
| Reply Drafts | Generate safe, editable reply candidates | Designed | `docs/06-solution-design.md` §6.5 | Unit tests |
| Policy & Risk | Validate mode and default write pause; future consent, limits, and opt-outs | Partial | `src/x_mutual_pilot/config.py`, `references/automation-policy.md` | `tests/test_config.py` |
| Approval & Execution | Approve, edit, reject, and safely execute actions | Designed | `docs/06-solution-design.md` §§6.7–6.8 | Integration tests |
| Audit & Monitoring | Record decisions, results, metrics, and alerts | Designed | `docs/06-solution-design.md` §10 | Integration tests |

Update only affected rows when implementation status or source locations change.
