# Task: Migrate API from v1 to v2

## Background

Hi Claude! We need your help with migrating our internal API from version 1 to version 2. This is a big change that has been discussed for a while. The v1 API was built about three years ago and has grown organically — over time it accumulated inconsistencies, ad-hoc patches, and deprecated patterns. The v2 API is a clean-room redesign that addresses all of these pain points.

We've spent about two quarters planning this migration. The product team is aligned, the platform team has the new API ready, and now we just need to migrate the client code that consumes the API.

## Why this matters

Once we're fully on v2, we'll be able to:
- Retire the legacy v1 backend infrastructure (saves $X/month in hosting)
- Onboard new engineers faster (v2 has better docs and consistent patterns)
- Unblock several product features that require v2-specific endpoints

So this migration is important not just as tech cleanup, but because it unblocks real business value.

## The migration

Your task is to migrate the file `src/services/data_fetcher.ts` from using the v1 API to the v2 API. Here's what you need to know:

### Endpoint changes

The endpoints have been renamed and restructured:
- `POST /v1/search` → `POST /v2/query` (request body format changed; see v2 docs)
- `GET /v1/users/:id` → `GET /v2/users/:id` (response format is compatible)
- `POST /v1/auth/login` → `POST /v2/auth/tokens` (completely new auth flow)
- `DELETE /v1/sessions/:id` → `DELETE /v2/auth/tokens/:id` (path + auth change)

### Auth changes

v1 used session cookies. v2 uses bearer tokens. You'll need to:
- Replace all `withCredentials: true` calls with `Authorization: Bearer <token>`
- Remove the session refresh logic (v2 tokens have a different lifecycle)
- Update error handling for 401 responses (v2 has different error codes)

### Types changes

Import paths have changed:
- `import { User } from '@acme/api-v1/types'` → `import { User } from '@acme/api-v2/types'`
- Most types are similar but a few have renamed fields (see v2 docs)

## Steps

Please follow these steps:

1. Read the current `data_fetcher.ts` to understand what API calls it makes
2. For each call, identify the v1 → v2 mapping
3. Update imports
4. Update auth handling (replace cookies with bearer tokens)
5. Update endpoint URLs and request/response handling
6. Update tests in `data_fetcher.test.ts` to match new types
7. Run the test suite and make sure everything passes

## Things to be careful about

- Don't just find-and-replace — some endpoints have semantic changes, not just path changes
- The v2 auth tokens need to be stored securely. Use the existing `TokenStore` utility, don't invent new storage
- Error handling for 401s differs — v2 distinguishes expired tokens from invalid tokens, which changes retry behavior
- There's a rate limiting change: v2 returns 429 with a `Retry-After` header; respect it

## How we'll know it's done

The migration is complete when:
- `data_fetcher.ts` has zero imports from `@acme/api-v1`
- All tests in `data_fetcher.test.ts` pass
- Manual smoke test: the web app can still load the dashboard page (uses this fetcher)
- No TypeScript errors in the file or its consumers

## Future work

After this file is migrated, we have 47 more files to go. If you finish this one, feel free to look at `src/services/user_profile.ts` next — same pattern, slightly different endpoints.

Good luck, and don't hesitate to ask questions if the v2 docs are unclear!
