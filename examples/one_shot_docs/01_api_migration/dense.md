# Goal

Migrate `src/services/data_fetcher.ts` from the v1 API to the v2 API.

# Endpoint mapping

- `POST /v1/search` → `POST /v2/query` (request body format changed)
- `GET /v1/users/:id` → `GET /v2/users/:id` (compatible responses)
- `POST /v1/auth/login` → `POST /v2/auth/tokens` (new auth flow)
- `DELETE /v1/sessions/:id` → `DELETE /v2/auth/tokens/:id`

# Steps

1. Read `data_fetcher.ts`; inventory v1 calls.
2. Update imports: `@acme/api-v1/types` → `@acme/api-v2/types`.
3. Replace `withCredentials: true` with `Authorization: Bearer <token>`. Remove session refresh.
4. Apply endpoint-by-endpoint changes per mapping above. Not all are path-only — some change semantics.
5. Update `data_fetcher.test.ts` for new types.
6. Run test suite.

# Hard constraints

- MUST use existing `TokenStore` utility for token storage. Do NOT invent new storage.
- MUST handle 429 with `Retry-After` header (v2 rate limiting).
- MUST distinguish expired vs invalid token on 401 (v2 changed error codes).

# Acceptance criteria

- Zero imports from `@acme/api-v1` in the file.
- All tests in `data_fetcher.test.ts` pass.
- No TypeScript errors in the file or its consumers.
- Dashboard page smoke test passes (uses this fetcher).

# Decision criteria

- If a v1 endpoint's semantic changed in v2: consult `docs/v2-migration.md` before rewriting.
- If v2 docs are ambiguous: stop and ask, do not guess.
