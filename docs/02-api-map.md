# API Map

All external operations use official APIs through dedicated adapters. Access
tiers, prices, scopes, and automation permissions must be revalidated before
live use.

| Capability | Method / direction | Authentication / guard | Source |
|---|---|---|---|
| Followers | `GET /2/users/:id/followers` | Bearer token, pagination, stop on errors | `src/x_mutual_pilot/x_api.py` |
| Following | `GET /2/users/:id/following` | Bearer token, pagination, stop on errors | `src/x_mutual_pilot/x_api.py` |
| User posts | `GET /2/users/:id/tweets` | Bearer token, `since_id`, deduplication | `src/x_mutual_pilot/x_api.py` |
| Mentions | `GET /2/users/:id/mentions` | Bearer token, explicit-intent source | `src/x_mutual_pilot/x_api.py` |
| Post lookup | `GET /2/tweets/:id` | Required immediately before reply | `src/x_mutual_pilot/executor.py` |
| Create reply | `POST /2/tweets` | User token plus all policy gates | `src/x_mutual_pilot/x_api.py` |
| Follow user | `POST /2/users/:id/following` | User token, approval, limits, idempotency | `src/x_mutual_pilot/x_api.py` |
| Draft reply | `POST /v1/responses` | Optional OpenAI key, `store: false` | `src/x_mutual_pilot/drafts.py` |

Do not add private endpoints, browser automation, or undocumented API behavior.
