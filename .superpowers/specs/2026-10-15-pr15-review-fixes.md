# PR #15 review round — design

**Status:** agreed in chat, 15 Oct 2026 · **Branch:** `fix/pre-wave-3` · **PR:** #15 (base `template-base`)

A last review of PR #15 (two passes: branch audit and code quality) found that the PR's
own rule — *a 401 means the request's credentials, nothing else* — still has three holes,
and that the code the PR wrote can be simpler. The user chose to fix both in this PR.

## The rule this round completes

The web retries a 401 once with a fresh token, then signs out. So every server failure
that is not the caller's credentials must answer something else. After this round:

| Failure | Status, `error_code` |
|---|---|
| No token, a bad token, a token for a user Clerk no longer has | 401 |
| Clerk rate-limits our provisioning call | 429 `CLERK_RATE_LIMIT` (its own status, no longer flattened) |
| Clerk refuses the server's own secret | 502 `CLERK_AUTH_ERROR` (its own status, no longer flattened) |
| Clerk's JWKS unreachable, `CLERK_ISSUER` not a URL, an unexpected verify error | 503 `AUTH_UNAVAILABLE` |
| Provisioning fails for an untyped reason (database, missing email) | 503 `USER_PROVISIONING_FAILED` |
| The server clock trails Clerk's by up to 5 s | accepted (leeway), not a 401 |

## Decisions

**D1 — a `ServiceUnavailableError` category (503, `SERVICE_UNAVAILABLE`)** in
`app/exceptions/base.py`. `server.md` §7 says every domain exception inherits the
category that fixes its status; four 503s set it by hand today. All four move under it,
keeping their `error_code`: `AuthUnavailableError`, `UserProvisioningError`,
`LLMServiceError` (and so its subclasses), `CategorisationUnavailableError`.
`DatabaseConnectionError` stays under `DatabaseError` (single inheritance; it is already 503).

**D2 — provisioning keeps a typed error's status.** `get_current_user` re-raises a
`ServiceError` as is and wraps only untyped failures in `UserProvisioningError`. One
exception: `ClerkUserNotFoundError` (404) becomes `AuthenticationError` (401) — a valid
token whose user Clerk no longer has was issued to a deleted user, which *is* a
credentials failure, and signing out is the right response. `UserAlreadyExistsError`
(409) passes through: a conflict is not an outage, and not the caller's credentials.

**D3 — `request.state.auth_error` replaces the `auth_unavailable` flag.** The
middleware stores the `AuthUnavailableError` it caught (declared `None` in its reset
block with the other keys); `get_clerk_id` raises it. The verifier's message and cause
chain reach the response, and `account` stops deciding what an outage maps to. A state
key is still the seam: a `ServiceError` raised inside a `BaseHTTPMiddleware` never
reaches FastAPI's handlers, and public routes must pass.

**D4 — a JWKS client that cannot be built is an outage.** `PyJWKClient` rejects a URL
without an http(s) scheme at construction (`CLERK_ISSUER=change-me`, `.env.example`'s
placeholder, or an empty one). The verifier builds the client before the token's `try`
and answers `AuthUnavailableError`, logging `token_jwks_client_invalid` at error.
`PyJWKClientError` from the key lookup stays a 401 (unknown `kid`); the empty-key-set
case it also covers remains the accepted minor listed in the PR.

**D5 — `leeway=5` on `jwt.decode`**, Clerk's own backend SDK default. Without it a
server clock behind Clerk's rejects a just-minted token (`iat`/`nbf` in the future), the
forced-refresh retry mints another one, and the user is signed out.

**D6 — a test sweeps every `ServiceError` subclass in `app.*`**: the ones with
`status_code == 401` must be exactly `AuthenticationError`, `InvalidCredentialsError`,
`InvalidWebhookSignatureError`.

**D7 — the LLM fallback is one loop.** `for offset in range(n)` from the start index,
one `except OpenAIError`, and after the loop one raise whose type follows the last error
(`RateLimitError` → `LLMRateLimitError`, `APITimeoutError` → `LLMTimeoutError`, else
`LLMAPIError`). `_next`, `models_tried`, the switch `try/break` and
`LLMFallbackExhaustedError` (raised nowhere else, referenced by no client) are deleted.
A failure to build a fallback client now propagates as itself rather than as
`LLMFallbackExhaustedError`; building the same registry's clients succeeded for the first.

**D8 — `structured_llm()` becomes a module-level `structured_llm_service`.** *Changed
from the chat proposal:* `ask_json` keeps its `service` parameter. It is the injection
point every structured-call test uses (`test_structured.py` passes a mock service), and
removing it would turn those tests into patches of a module global. Only the factory goes.

**D9 — the provider's waiter moves into a `useSessionWait(isSignedIn)` hook, unchanged
in mechanism.** *Changed from the chat proposal:* a single deferred promise is not fewer
pieces once it must be re-armed when a session ends (cross-tab sign-out, then sign-in in
the same document), and the current Set-of-waiters already clears each timer on wake.
The gain worth having is the shape: the provider reads as the vendor mapping, and
`getToken` becomes three lines. The mechanism that passed the hand check is kept.

**D10 — `@app/auth`'s surface shrinks to what is used.** `isSignedIn` leaves the
context; `SESSION_WAIT_MS` and `GetTokenOptions` leave `index.ts` (the test imports the
constant from `./provider`). `apps/web/README.md`'s field list is then correct as it stands.

**D11 — `first-query-after-sign-in.test.tsx` stays in `apps/web`.** *Changed from the
review's suggestion:* `@clerk/nextjs` is not resolvable from `packages/api-client`
(pnpm isolates it; `vi.mock` would miss the module `@app/auth` imports). Its stale
`BUGS.md` pointer and its 20 ms sleep are fixed in place.

**D12 — docs follow the code**: `server.md` §7 table and rule, `clerk.md` symptom rows
(misconfigured issuer, clock skew), `authentication.md` §2 (leeway), `web-app.md`
(`isSignedIn` row), the codegen guide's copy of `useApiRequest` resynced (the guide is a
rebuild guide and keeps full listings), the `server-patterns` skill's exception tree,
`handlers.py`'s count of LLM causes, and a `TODO.md` entry for the per-call fallback's
cost during a default-model outage (every call re-pays the retry ladder; a deliberate
trade-off of the concurrency fix).

## Out of scope

The empty-JWKS-key-set 401, the outage's three log lines per request (now documented
correctly in the PR body), parallel `skipCache` mints on concurrent 401s, and a sticky
"last healthy model" hint.
