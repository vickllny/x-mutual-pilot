# Page and Route Map

No UI, route configuration, or navigation code exists yet.

| Planned surface | Entry | Purpose | Source |
|---|---|---|---|
| Approval queue | Operator console | Review, edit, approve, reject, or snooze candidates | Not implemented |
| Action detail | Approval queue item | Show target, rationale, risks, draft history, and expiry | Not implemented |
| Operations status | Operator console | Display mode, write pause, quotas, metrics, and alerts | Not implemented |

The expected flow is:

```text
Candidate discovery -> Approval queue -> Review/edit -> Approve or reject
-> Policy recheck -> Execution -> Audit result
```

Add concrete paths, components, and navigation entries only after a UI framework
and route structure are selected.
