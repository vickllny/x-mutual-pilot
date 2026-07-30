# Feature Map

This repository is in the solution-design stage; no executable modules exist yet.

| Module | Planned feature | Status | Main reference | Planned tests |
|---|---|---|---|---|
| X Adapter | Official API access, OAuth, pagination, rate-limit handling | Designed | `docs/06-solution-design.md` §6.1 | Contract tests |
| Relationships | Sync followers/following and calculate mutuals | Designed | `docs/06-solution-design.md` §6.2 | Unit and integration tests |
| Post Watcher | Discover and filter new posts from mutuals | Designed | `docs/06-solution-design.md` §6.3 | Unit and integration tests |
| Follow-back | Score new followers and explain recommendations | Designed | `docs/06-solution-design.md` §6.4 | Unit tests |
| Reply Drafts | Generate safe, editable reply candidates | Designed | `docs/06-solution-design.md` §6.5 | Unit tests |
| Policy & Risk | Enforce consent, limits, opt-outs, and write pauses | Designed | `docs/06-solution-design.md` §6.6 | Unit and integration tests |
| Approval & Execution | Approve, edit, reject, and safely execute actions | Designed | `docs/06-solution-design.md` §§6.7–6.8 | Integration tests |
| Audit & Monitoring | Record decisions, results, metrics, and alerts | Designed | `docs/06-solution-design.md` §10 | Integration tests |

Update only affected rows when implementation status or source locations change.
