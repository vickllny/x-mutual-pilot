# Page and Route Map

The management UI is a loopback-only standard-library HTTP application.

| Surface | Route | Purpose | Source |
|---|---|---|---|
| Dashboard | `GET /` | Counts, mode, pause state, and review queue | `src/x_mutual_pilot/web.py` |
| Approve | `POST /candidates/:id/approve` | Preserve original draft and approve edits | `DashboardApp.handle_action` |
| Reject | `POST /candidates/:id/reject` | Reject and append an audit event | `DashboardApp.handle_action` |
| Snooze | `POST /candidates/:id/snooze` | Hide for one hour, then return to pending | `DashboardApp.handle_action` |
| Pause | `POST /pause` | Persist the emergency write pause | `DashboardApp.handle_action` |

```text
Discovery -> Review queue -> Edit / approve / reject / snooze
-> CLI confirmation -> Policy recheck -> X execution -> Audit result
```

All mutations require a per-process CSRF token. The server refuses non-loopback
binding. Resume and live execution are intentionally CLI-only confirmation flows.
