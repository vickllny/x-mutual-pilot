# API Map

All external operations are planned through the official X API via a single
adapter. Exact endpoint versions, access tiers, prices, scopes, and automation
permissions must be revalidated before implementation.

| Capability | Direction | Authentication / guard | Reference |
|---|---|---|---|
| Current account | Read | OAuth, minimum read scope | `docs/06-solution-design.md` §6.1 |
| Followers / following | Read | OAuth, pagination, quota tracking | §6.2 |
| Follow activity | Inbound event | Subscription and webhook validation | §§6.2, 7.1 |
| Posts / filtered stream | Read or inbound event | Rule maintenance, deduplication | §§6.3, 7.2 |
| Create reply | Write | Approval, policy recheck, limits, idempotency | §§6.8, 7.2 |
| Follow user | Write | Score, approval, relationship recheck, limits | §§6.8, 7.1 |

Do not add private endpoints, browser automation, or undocumented API behavior.
