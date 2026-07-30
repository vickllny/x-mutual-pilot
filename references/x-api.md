# X API Reference

Reviewed against official X documentation on 2026-07-30.

## Implemented endpoints

| Purpose | Method and path | Authentication |
|---|---|---|
| Read followers | `GET /2/users/:id/followers` | Bearer token |
| Read following | `GET /2/users/:id/following` | Bearer token |
| Read user posts | `GET /2/users/:id/tweets` | Bearer token |
| Read mentions | `GET /2/users/:id/mentions` | Bearer token |
| Revalidate post | `GET /2/tweets/:id` | Bearer token |
| Follow user | `POST /2/users/:id/following` | OAuth user access token |
| Create reply | `POST /2/tweets` | OAuth user access token |

The adapter follows `meta.next_token`, rejects partial errors, detects repeated
pagination tokens, and does not retry writes. Treat all IDs and tokens as opaque
strings. Keep credentials out of errors and logs.

## Reply restriction

For self-serve API access, only send a reply when the original author explicitly
summoned the replying account through a mention or qualifying quote. A follow or
an unrelated mutual post is not sufficient intent.

AI-generated replies set `made_with_ai: true`. Every reply rechecks that the
source post still exists immediately before the write.

## Change checklist

- Recheck access tier, OAuth scopes, fields, prices, and rate limits.
- Preserve pagination-loop and partial-response detection.
- Add fake-response contract tests before changing payload parsing.
- Never add browser automation or undocumented endpoints.

Official references:

- https://docs.x.com/x-api/users/follows/introduction
- https://docs.x.com/x-api/posts/timelines/introduction
- https://docs.x.com/x-api/posts/manage-tweets/introduction
- https://docs.x.com/x-api/posts/get-post-by-id
