# X API Read-Only Reference

Reviewed against official X documentation on 2026-07-30.

## Implemented endpoints

| Purpose | Method and path | Authentication |
|---|---|---|
| Read followers | `GET /2/users/:id/followers` | Bearer token |
| Read following | `GET /2/users/:id/following` | Bearer token |

The client requests `id,name,username,protected,verified`, follows
`meta.next_token`, and stops immediately on HTTP errors. It never sends a write
request.

## Response assumptions

```json
{
  "data": [{"id": "123", "username": "example", "name": "Example"}],
  "meta": {"next_token": "opaque-token"}
}
```

Treat IDs and pagination tokens as opaque strings. Do not derive identity from a
username because it can change.

## Change checklist

- Recheck endpoint availability, access tier, scopes, fields, and rate limits.
- Preserve pagination-loop detection.
- Keep authorization headers and tokens out of errors and logs.
- Add fake-response contract tests before changing response parsing.

Official references:

- https://docs.x.com/x-api/users/follows/introduction
- https://docs.x.com/x-api/overview
