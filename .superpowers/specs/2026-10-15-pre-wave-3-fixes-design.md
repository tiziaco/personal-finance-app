# Fixes before wave 3 — Design

**Date:** 2026-10-15
**Status:** Approved in brainstorming; awaiting spec review
**Branch:** `fix/pre-wave-3`, PR into `template-base`

---

## Goal

Four defects the user chose on 15 Oct 2026, closed before wave 3 (5b, 6, 7) builds on the
code they live in, plus one addition the user approved in brainstorming:

1. The first page load after sign-in fires its queries without a token (`docs/BUGS.md`).
2. `LLMService` keeps its fallback position on itself (`docs/TODO.md`, CSV import follow-ups).
3. The import accepts dates analytics cannot read (`docs/TODO.md`, same section).
4. Income and expenses have no colours of their own (`docs/TODO.md`, Web).
5. **Scope addition, approved by the user:** a 401 is handled as an auth event: one retry
   with a fresh token, then sign-out. The server's 401 is narrowed to mean bad credentials
   and nothing else, which 5 needs.

Success: signing in and landing on `/transactions` or `/home` shows data on the first
render, with no 401 in the server log; concurrent LLM calls on one service each walk the
registry from the default; a row dated 2205 is rejected with a reason; the trend chart draws
income and expenses in a validated pair no other chart uses; a session that is really over
ends on `/sign-in` instead of "Something went wrong".

## Decisions

| # | Decision |
|---|---|
| D1 | The 401 race is fixed at the auth seam: `@app/auth`'s `getToken` resolves only once the session state is settled. Rendering is not gated. |
| D2 | A 401 gets one retry with a forced-fresh token. A second 401 calls `signOut()`, single-flight. |
| D3 | The server answers 401 only for missing or invalid request credentials. A provisioning failure is 503; the server's own Clerk credential being rejected is 502. |
| D4 | `LLMService` keeps the model index and client in locals for each call. No fallback position survives a call; every call starts from the default, or from the pinned model. |
| D5 | `MIN_DATE`/`MAX_DATE` move to `app/modules/transaction/domain/dates.py`, exported from the `transaction` package root. Analytics imports them from there. |
| D6 | Income is green, expenses violet: new tokens `--chart-income` and `--chart-expense`. |

---

## 1. The token waits for the session (D1)

**Cause.** Clerk's `useAuth().getToken` already waits for clerk-js to load; it returns `null`
when, once loaded, `clerk.session` is empty. Straight after sign-in, the dashboard mounts
inside that window. The expected mechanism is that `setActive` navigates to the redirect
before it installs the new session; the hand repro confirms or corrects this, and the
`BUGS.md` resolution records what was seen. The design holds either way: it waits for
`isSignedIn`, which covers both "not loaded" and "loaded, no session yet".

**Why not gate rendering.** `ClerkProvider` is not `dynamic`, so the server render has no
session. Gating `QueryProvider`'s children on `isSignedIn` would blank the dashboard on every
hard load until clerk-js loads. Default `enabled: false` on the `QueryClient` is overridden by
orval's own `enabled` on hooks with path params, so it would not cover every query.

**Design.** In `packages/auth/src/provider.tsx`, `AuthProvider` wraps Clerk's `getToken`:

1. Ask Clerk. A token comes back: return it.
2. `null`, and `isSignedIn` is false: wait until `isSignedIn` turns true, then ask Clerk
   again. `isSignedIn` is read from a ref, and waiters are resolved from an effect on
   `isSignedIn`.
3. No session within `SESSION_WAIT_MS` (5 s): return `null`. The request goes out bare and
   meets D2's handling.

`AuthContextValue` gains `isSignedIn: boolean`. `getToken` takes an optional
`{ forceRefresh?: boolean }`, mapped to Clerk's `skipCache` (for D2). The docstring states the
new contract: a token, or `null` only once the state has settled.

`packages/api-client` is untouched by D1: `useApiRequest` still calls `getToken()`.

**Tests (written to fail first).**
- `packages/auth/src/provider.test.tsx`, with Clerk's `useAuth` mocked: `getToken` while
  `isSignedIn` is false stays pending; re-rendering with `isSignedIn` true and a token
  resolves it to that token. With fake timers, no session within `SESSION_WAIT_MS` resolves
  `null`. A token on the first ask returns without waiting.
- `packages/api-client`: a query rendered under `QueryProvider` and a mocked `@app/auth`
  whose `getToken` follows the same wait sends no `fetch` before the session exists, then
  exactly one request carrying `Authorization` once it does.

**Hand check.** Sign out, sign in, land on `/transactions`, then repeat for `/home`. The
table and the dashboard render data, and the server log shows no `no_auth_header_present`
for those requests.

## 2. A 401 is an auth event (D2, D3)

### Server: 401 means bad credentials

- `get_current_user` (`server/app/modules/account/dependencies.py`) wraps any provisioning
  failure in `AuthenticationError("Failed to provision user")`. It raises a new
  `UserProvisioningError` instead: status 503, code `USER_PROVISIONING_FAILED`, in
  `app/modules/account/exceptions.py`.
- `ClerkAuthenticationError` (`server/app/integrations/clerk/exceptions.py`) is the server's
  own Clerk secret being rejected. Its status becomes 502; the code `CLERK_AUTH_ERROR` stays.
- The missing-credentials path (`get_clerk_id` raising `AuthenticationError`) stays 401.
- If any route declares these responses, `make gen-contract` regenerates the spec and client.

Tests: a provisioning failure answers 503 with `USER_PROVISIONING_FAILED`; a rejected Clerk
secret maps to 502; a request with no token still answers 401.

### Client: retry once, then sign out

In `packages/api-client/src/use-api-fetch.ts`, `useApiRequest`:

1. Send with `getToken()`.
2. A 401: ask `getToken({ forceRefresh: true })` and send once more. A 401 means the server
   ran no handler, so replaying a POST, a FormData upload or the chat stream is safe. Bodies
   in this app are strings or FormData, which replay; a `ReadableStream` body is not, and is
   not used.
3. A second 401: call `useAppAuth().signOut()` once for the page, guarded by a module-level
   in-flight flag so many failing queries sign out once. The `ApiError` still throws to the
   caller. `signOut()` ends the Clerk session, then loads `/sign-in` as a new document; ending
   the session is what stops `/sign-in` bouncing back to the dashboard in a loop.

The 401 toast ("session expired") stays as it is; the document load to `/sign-in` replaces
the page. `meta.silentError` is unaffected. `QueryProvider`'s retry rule is unchanged: it does
not retry a 4xx, and the 503 from D3 is a 5xx, which it retries once.

Tests in `use-api-fetch.test.ts`: a 401 then a 200 retries with a forced-fresh token and
resolves; two 401s call `signOut` once and reject with the `ApiError`; concurrent double-401s
call `signOut` once; a 403 neither retries nor signs out.

## 3. `LLMService`'s position is per call (D4)

**Cause.** `_current_model_index` and `_llm` live on the service, but each call counts its
attempts locally. Calls running at once on one service each move the shared position, so a
call can skip models and use up its attempts without reaching a healthy one, and the position
stays wherever it ended. `call(model_name=...)` swaps `self._llm` and restores it afterwards,
which races with any concurrent call in the same way.

**Design** (`server/app/integrations/llm/service.py`):
- `_call_llm_with_retry(llm, messages, config)` takes the client as a parameter.
- `_call_with_fallback(messages, config, start_index, start_llm)` keeps `index` and `llm`
  as locals and advances them through a pure helper returning the next index and its
  resolved client. Nothing on `self` changes during a call.
- `call()` passes the default (`self._default_index`, `self.get_llm()`) or the pinned model.
  The save and restore go away.
- `get_llm()` and `current_model_name()` keep returning the default. The chatbot uses them
  for token counting, the inference-time metric label and the title model.
- `_current_model_index` is renamed `_default_index`. It is set once in `__init__`.
- `structured_llm()` still builds a tool-less service. Its docstring loses the "its own
  fallback position" reason. `test_each_import_rotates_its_own_model_fallback` is deleted:
  the property it guards no longer exists.

**Consequence, accepted by the TODO's fix:** during an outage of the default model, every call
retries the default before moving on, where before a rotation stuck.

**Tests.** The new test runs several `call()`s concurrently (`asyncio.gather`) on one service.
Its fake clients yield between attempts and fail on chosen models. Each call must try the
registry in order from the default, without skipping one, and the service still names the
default afterwards. A second case runs a pinned call concurrently with a default call: each
starts on its own model. The tenacity waits are disabled the way the existing service tests
do it. Existing tests that read or set `_current_model_index` move to the new shape.

## 4. The import rejects a date analytics cannot read (D5)

- New `server/app/modules/transaction/domain/dates.py` holds `MIN_DATE = date(1900, 1, 1)` and
  `MAX_DATE = date(2100, 12, 31)`, with the comment explaining the range, which moves from
  `analytics/schemas.py`. Both are exported from `app/modules/transaction/__init__.py`.
- `analytics/schemas.py`, `analytics/service.py` and `analytics/dependencies.py` import them
  from `app.modules.transaction`. R6 puts `analytics` above `transaction` and R1 sends the
  import through the package root, so `lint-imports` stays green.
- `transaction/imports/domain.py`, after a date parses: outside the bounds means
  `Rejection(row.number, f"date out of range “{_shown(raw_date)}”")`, through the existing
  rejection path.

Tests: the domain's row reading accepts `MIN_DATE` and `MAX_DATE` and rejects the day before
and the day after, each with the reason. `lint-imports` passes.

## 5. Income and expense colours (D6)

The validated pair, chosen by the user over green and red (red sits 7.1 ΔE from the donut's
orange slot and echoes `--destructive`) and violet and red (collides with both blue and
orange):

| Token | Light | Dark |
|---|---|---|
| `--chart-income` | `#008300` | `#008300` |
| `--chart-expense` | `#6250d6` | `#9085e9` |

`dataviz` validator, run on the app's card surfaces (light `#ffffff`, dark `#161b1d`):
every check passes in both modes. CVD ΔE is 28.8 light and 26.9 dark; normal-vision ΔE is
35.5 light and 34.0 dark; both colours are at least 3:1 against the surface.

- `packages/ui/src/styles/globals.css`: both tokens in `:root` and `.dark`, and
  `--color-chart-income`/`--color-chart-expense` in `@theme`.
- `apps/web/src/components/dashboard/trend-chart.tsx`: the config's `income` and `expenses`
  take the new tokens. The legend reads them from the config already.
- They are the only income or expense marks on the dashboard. The summary cards'
  `text-destructive` marks a negative value, not a series, and stays.

Hand check: `/home` in light and dark mode, screenshot reviewed.

---

## Out of scope, reported to the user

- A transaction added by hand is not held to `MIN_DATE`/`MAX_DATE`, so a typo year drops out
  of the charts the same way.
- After a fallback, the chatbot's metric label and stored model name are the default model's,
  not the one that answered.

## At PR time

- Delete the `BUGS.md` entry and the three `TODO.md` entries this closes.
- `docs/architecture/web-app.md`: the token contract (D1) and the 401 handling (D2).
  `docs/architecture/server.md` (or the errors guide it points to): what 401, 502 and 503 mean
  (D3). The date bounds' home (D5), where the data-model or analytics doc describes the range.
- Roadmap row: `complete — [PR #N](url) into template-base; reaches main at Cutover`.
- Delete this spec and the plan.
