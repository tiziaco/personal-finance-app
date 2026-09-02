# WS5 — Typed API Client Codegen

**Date:** 2026-09-01
**Status:** Approved, not implemented
**Supersedes:** the WS5 section of `2026-08-24-template-hardening-design.md`
**Input:** `docs/api-client-codegen-setup.md` — the portable rebuild guide extracted
from another project. This spec corrects it against the measured state of this repo;
the guide is updated to match once WS5 ships.

---

## Problem

API access is hand-written. `lib/api/health.ts` plus `hooks/use-server-status.ts`,
duplicated across both portals, is the entire surface — four files, one endpoint.

The response type is hand-maintained in `@app/types`, and **it has already drifted**.
`HealthResponse` declares `agents` as a fixed `{ chatbot: { ready, graph_compiled } }`.
The handler at `app/api/system/health.py` builds a dict keyed by agent name and, in the
failure branch, inserts `agents_status["error"] = "Agents not initialized"` — a string
where every sibling value is an object. Nothing caught this, because nothing can: the
type and the handler share no source.

Migration cost is at its floor right now (one hook, no forms, no mutations consumed by
UI), and no feature work is planned before the B2C fork. The cost only rises.

---

## Measured baseline

Established by running the export, not by reading the code. `app.openapi()` completes
in 3.6s with no database, no `.env` file, and no secrets — so every guardrail below is
cheap and offline.

| Fact | Consequence |
|---|---|
| 11 paths, 4 tags: `auth`, `chatbot`, `conversation`, `system` | Small enough that the whole surface is reviewable in one diff |
| `webhooks` router already carries `include_in_schema=False` | Server-to-server routes are correctly absent; no work needed |
| Every `/api/v1/*` route has an explicit camelCase `operation_id` | `getMe`, `listConversations` — the guide's snake_case examples do not match this repo |
| `/`, `/health`, `/ready` are annotated `Dict[str, Any]` | Emit `additionalProperties: true` → orval generates `{[key: string]: unknown}` |
| Those three routes have no explicit `operation_id` | orval would emit `useReadinessCheckReadyGet`, `useHealthCheckHealthGet`, `useRootGet` |
| `streamChatMessage` is SSE with an empty response schema | orval would emit a `useStreamChatMessage` mutation returning `unknown` |
| `deleteConversation`, `clearChatHistory` return 200 with no schema | Generate `unknown`; `deleteMe` already does this correctly with `status_code=204` |
| `useAppAuth()` returns `{ user, role, isLoaded }` — no `getToken` | The guide's `const { getToken } = useAppAuth()` does not exist |
| `use-server-status.ts` imports `useAuth` from `@clerk/nextjs` | Violates `@app/auth`'s own docblock rule and standing constraint #1 |
| Only `NavItem` and `HealthResponse` are imported from `@app/types` | `Project`, `Supplier`, `Document`, `PurchaseOrder` and their enums have zero importers |
| `prettier` is not a dependency anywhere in the workspace | orval's `prettier: true` would fail on a clean install |
| No `.github/`, no hook tooling; one `scripts/verify-infra.sh` | The guide's drift-guard CI job does not exist and must be built |
| `moduleResolution: "bundler"` in every tsconfig | Wildcard subpath exports resolve correctly |

**The consequence that decides the shape of WS5:** the single endpoint this workstream
exists to migrate is the one whose schema is untyped. Shipping the guide as written
would replace a hand-written `HealthResponse` with `{[key: string]: unknown}` — a net
regression in the only place anyone would notice.

---

## Decisions

**D-1. The backend owns the contract.** `server/openapi.json` is a committed artifact
and the hand-off boundary. Everything on the frontend side of it is generated and
committed. A hand-written type describing a request or response body is a defect.
Inherited from the guide, unchanged.

**D-2. The mutator is a hook, not a module singleton.** orval supports a mutator whose
name begins with `use`, and calls it inside each generated hook. This deletes, in one
move: the module-level `_instance` singleton, `ApiClientProvider`, the load-bearing
`Auth → ApiClient → Query` provider ordering, the synchronous `useRef` guard that exists
only to beat a first-render race, the init-before-use throw, and the stale `getToken`
closure captured on first render.

It also removes a leak class that prose cannot mitigate. A module-scope client in a
Next.js App Router process is shared across concurrent requests; in a multi-tenant
application that is one tenant's token serving another tenant's request. The guide files
this under "single-tenant caveat". For this repo it is a defect, not a caveat.

**Trade-off accepted:** with a hook mutator, orval emits the bare fetchers as hooks too
(`useListXHook()`), so calling an endpoint outside React — RSC prefetch, route handler,
server action — needs its own hand-written path. This repo has no such call today, and
the guide's §6.6 pattern for unauthenticated routes is already plain `fetch` plus the
generated Zod schema, so it composes. **Trigger to revisit:** the first RSC prefetch or
`HydrationBoundary`; at that point add an explicit non-hook fetcher rather than
reinstating the singleton.

**D-3. `includeHttpResponseReturnType: false`.** The guide's §9.1 presents the
response-envelope mismatch as a choice between rewriting the mutator to return
`{ data, status, headers }` and hiding a cast in an `unwrap<T>()` helper. Neither is
needed: orval has a configuration flag that makes the generated types resolve the body
directly, which is what the mutator returns. Zero casts, no helper, no mutator rewrite.
§9.1 is deleted from the guide rather than answered.

**D-4. The token comes from `@app/auth`, never from Clerk directly.** `AuthContext`
gains `getToken`, and `useApiFetch` consumes it via `useAppAuth()`. This keeps
`@app/api-client` depending on the portability seam rather than on a specific auth
provider, satisfies standing constraint #1, and repairs the existing violation in both
copies of `use-server-status.ts`. In the B2C fork, `AuthProvider`'s internals change and
`api-client` does not.

**D-5. `@app/types` is deleted.** `NavItem` moves to `@app/ui` — a nav contract typed by
`LucideIcon` is a UI contract, and `@app/ui` is its only structural consumer.
`HealthResponse` becomes generated — note that the TypeScript type of that name
describes `/ready`, so its replacement is the generated `ReadinessResponse`, not the
identically named Pydantic model added for `/health`. The six unimported domain types
are removed: they describe endpoints that do not exist, and under D-1 they will be
generated when those endpoints do.

This is not tidying. Keeping a package named `types` that mirrors API schemas next to a
generated `types/` directory leaves the rule "never mirror an API schema" enforced by
prose, with a live counterexample beside it — and carries Rilevio-specific dead weight
across the B2C fork.

**D-6. Generated code lives under one `src/generated/` tree.** `clean: true` wipes its
targets on every run. In the guide's flat layout, hand-written `index.ts` and
`custom-instance.ts` sit as siblings of three directories that get deleted — a footgun
guarded only by §9.3's warning. A single generated parent makes "never hand-edit"
visible in the path and makes the accident structurally impossible.

**D-7. Server contract prerequisites ship with a written convention.** Fixing four
routes makes today's output correct; writing the rule down is what stops the next
endpoint reintroducing an untyped response, and it is what crosses the fork.

**D-8. SSE is excluded by tag, not hidden from the schema.** `streamChatMessage` takes a
per-route `tags=["streaming"]` override and orval filters that tag out.
`include_in_schema=False` would also work and is simpler, but it removes the route from
Swagger, where it is legitimately documented for manual consumption. This interlocks
with WS7 (SSE disconnect handling), which will own the hand-written stream client.

**D-9. The drift guard is one script with two callers.** `scripts/check-contract.sh`
regenerates both artifacts and fails on a non-empty `git diff`. `make check-contract`
runs it locally; a GitHub Actions workflow runs the same target on pull requests. The
export needs no DB, no `.env` and no secrets, so the CI job requires nothing configured.

Without this guard the committed-artifact model is unsound: `openapi.json` silently
rots, and the frontend eventually compiles against a contract the backend stopped
serving. This is the workstream's most important deliverable after the client itself.

**D-10. orval is pinned to an exact version.** Not `^7.0.0`. The generated tree is
committed; a caret means a routine `pnpm install` rewrites hundreds of tracked files
with no intent behind the change.

**D-11. The array-param serializer patch is not ported.** The guide's §5 carries a regex
rewrite of generated output, fixing orval's fetch template serializing
`?status=A,B` instead of `?status=A&status=B`. No endpoint in this repo takes an array
query parameter. A regex over generated code, for a bug that cannot occur, in a template
about to be forked twice, is maintenance liability rather than safety. The guide keeps
§9.2 as a documented hazard plus the regression test it prescribes.
**Trigger to add it:** the first `List[T] = Query(...)` parameter.

**D-12. Query error toasts are gated on first load; 4xx is not retried.**
`QueryCache.onError` fires on every failed query, background refetches included, and
`useServerStatus` polls `/ready` every 30 seconds — ungated, an outage produces a toast
every 30 seconds indefinitely. Toasts fire only when `query.state.data === undefined`,
and a query may opt out entirely through `meta: { silentError: true }`, which
`onError` checks before toasting. The health poll opts out: a widget
already rendering "degraded" does not also need a toast. Separately, `retry: 1` spends a
second request on every 401 and 404; it becomes a predicate that retries only 5xx.

---

## Architecture

```
FastAPI app
   │  app.openapi()            no DB, no secrets, 3.6s
   ▼
server/openapi.json            ← committed artifact, the contract boundary
   │                             filters: exclude tag "streaming"
   ├─ target 1 (react-query) ─► packages/api-client/src/generated/endpoints/<tag>/<tag>.ts
   │                            packages/api-client/src/generated/types/*.ts
   └─ target 2 (zod) ────────► packages/api-client/src/generated/zod/<tag>/<tag>.ts
   │
   ▼  scripts/postgen.mjs       barrels only — clean:true wipes them every run
   │
   ▼
apps/*  import  @app/api-client/endpoints/<tag>
                @app/api-client/types
                @app/api-client/zod/<tag>
```

Two commands, and **both outputs land in the same commit**:

```bash
cd server  && make export-openapi
cd web-app && pnpm --filter @app/api-client gen:api
```

Splitting the export from the regeneration across commits is the failure mode
`make check-contract` exists to catch.

---

## Server contract layer

### Export

`server/scripts/export_openapi.py` and a `make export-openapi` target, writing
`indent=2, sort_keys=True` for deterministic diffs. Verified to run offline.

**Known wart, accepted:** `app.main` is not import-side-effect-free. `Langfuse(...)` is
constructed at module scope and prints an authentication warning without a key; the LLM
service initialises five model entries. This is stderr noise, the JSON is written to a
file, and the export succeeds. Cleaning it up belongs to whichever workstream touches
application startup.

### Typed system responses

New `app/schemas/system.py` — `RootResponse`, `HealthResponse`, `ReadinessResponse` —
declared as `response_model` on `/`, `/health` and `/ready`. `/ready` additionally
declares `responses={503: {"model": ReadinessResponse}}`, since its degraded path
returns `JSONResponse(status_code=503)` and the schema currently describes no 503 at all.

The three names collide with intent: the existing TypeScript `HealthResponse` describes
`/ready`, not `/health`. `ReadinessResponse` is the model that replaces it.

`ReadinessResponse` must resolve the drift recorded under Problem:

```python
agents: dict[str, AgentStatus]      # keyed by agent name; values are always objects
agents_error: str | None = None     # set when agents never initialised
```

**The design commits to not reproducing the polymorphic dict** — a value that is an
object on the success path and a bare string on the failure path is not modellable, and
is precisely why the hand-written type was wrong. The handler changes to populate
`agents_error` instead of writing `agents_status["error"]`.

### Explicit operation ids

`getRoot`, `getHealth`, `getReadiness` on the three system routes — camelCase, matching
the existing `getMe` / `listConversations` convention.

### Streaming tag

`streamChatMessage` takes a per-route `tags=["streaming"]` override. It remains in
Swagger; orval excludes the tag.

### Status codes

`status_code=204` on `deleteConversation` and `clearChatHistory`, matching `deleteMe`.

### The convention

A new **API contract** section in `server/CLAUDE.md`:

- Every route declares an explicit tag.
- Every route declares an explicit camelCase `operation_id`.
- Every route declares either a `response_model` or `status_code=204`.
- Server-to-server routes declare `include_in_schema=False` (webhooks already does).
- `operation_id` is a public frontend symbol. Renaming a handler is a breaking change.
- The spec export and the client regeneration land in the same commit.

**Scope boundary:** no new endpoints, no service or repository changes. Route
decorators, three schema classes, one documentation section.

---

## The `@app/api-client` package

```
web-app/packages/api-client/
├── orval.config.ts
├── package.json
├── tsconfig.json
├── scripts/postgen.mjs
└── src/
    ├── index.ts          ← hand-written: public runtime surface
    ├── use-api-fetch.ts  ← hand-written: the mutator
    ├── errors.ts         ← hand-written: ApiError
    └── generated/        ← orval owns this entire tree; never hand-edited
        ├── endpoints/<tag>/<tag>.ts
        ├── types/*.ts
        └── zod/<tag>/<tag>.ts
```

Private, unpublished, ships raw TypeScript (`main` and `types` → `./src/index.ts`).
Subpath exports:

```
"."              → ./src/index.ts
"./endpoints/*"  → ./src/generated/endpoints/*/index.ts
"./types"        → ./src/generated/types/index.ts
"./zod/*"        → ./src/generated/zod/*/index.ts
```

`react` is a peer dependency — the package must never resolve its own React copy.
`prettier` is added as a devDependency, since orval's `prettier: true` shells out to a
local binary that this workspace does not currently have.

### orval.config.ts

Two targets over one input:

- **Input** (shared): `../../../server/openapi.json` with
  `filters: { mode: "exclude", tags: ["streaming"] }`.
- **Target 1** → `src/generated/endpoints`, `schemas: src/generated/types`,
  `client: "react-query"`, `httpClient: "fetch"`, `mode: "tags-split"`, `clean: true`,
  `prettier: true`, `override.fetch.includeHttpResponseReturnType: false`,
  `override.mutator: { path: "./src/use-api-fetch.ts", name: "useApiFetch" }`.
- **Target 2** → `src/generated/zod`, `client: "zod"`, `mode: "tags-split"`,
  `clean: true`, `prettier: true`.

### postgen.mjs

One Node script, replacing the guide's bash wrapper around a heredoc'd Node program —
which will not run on Windows, in a repository whose purpose is to be forked. Its only
responsibility in WS5 is regenerating the barrel `index.ts` files that `clean: true`
removes on every run.

### The mutator

`useApiFetch()` returns a `useCallback`'d fetcher that:

1. Prefixes relative URLs with the base URL; absolute URLs pass through untouched.
2. Attaches `Authorization: Bearer <token>` unless the caller already set one.
3. Sets `Content-Type: application/json` only for plain bodies — never for `FormData`
   (the browser must set its own multipart boundary), `Blob`, or `ArrayBuffer`.
4. Throws `ApiError` on any non-2xx. This is the only error type the app layer knows.
5. Returns `undefined` for 204 and zero-length responses; parses JSON; falls back to text.

Two couplings, both deliberate and both documented in the package:

- The token comes from `useAppAuth()` (D-4), so the package depends on `@app/auth`, not
  on Clerk.
- `baseUrl` reads `process.env.NEXT_PUBLIC_API_URL` inside the package. This is the
  package's one Next.js coupling; `transpilePackages` inlines it. Both portals and the
  B2C fork are Next.js applications.

---

## Runtime wiring

**The provider tree loses a layer:**

```
ClerkProvider → AuthProvider → QueryProvider → ThemeProvider
```

`ApiClientProvider` does not exist. There is no ordering requirement beyond
`AuthProvider` above anything that issues a query, which React's own rules already
enforce.

**`@app/auth`** gains `getToken` on `AuthContext`, sourced from Clerk's `useAuth()`
inside `AuthProvider` — the one place in the frontend permitted to call it.

**`@app/types` is removed** from both `next.config.ts` `transpilePackages` lists, both
apps' `package.json`, `@app/ui`'s `package.json`, and the `web-app/Dockerfile` deps
stage. `@app/api-client` is added to each of those.

The Dockerfile edit is easy to miss and fails loudly but confusingly: the deps stage
copies each workspace `package.json` by name, so omitting the new one breaks the image
build on a lockfile mismatch rather than on a missing file.

**One migration.** `useServerStatus` is rewritten on the generated `useGetReadiness`;
`lib/api/health.ts` is deleted from both portals. The `auth`, `conversation` and
`chatbot` hooks generate but nothing consumes them — WS5 builds no UI.

**Deliberately not created:** `apps/*/src/hooks/api/`. The guide's §7 wrapper convention
(one file per mutation, owning cache invalidation, keys always from generated
`getXQueryKey()` helpers, never toasting generically) is documented for the first
mutation to follow. The directory is not scaffolded, because there are no mutations.

---

## Error handling

`ApiError` carries `{ message, status, body, requestId }`, reading `X-Request-ID` from
the response. `CorrelationIdMiddleware` already stamps every request and binds the id to
the server's structured logs, so this makes any client-side error traceable to a server
log line for the cost of one header read.

`QueryProvider` changes:

- **`ReactQueryDevtools` is kept.** The guide's version drops it; both portals have it.
- **`QueryCache.onError` is gated** on `query.state.data === undefined`, with a `meta`
  opt-out. The health poll opts out (D-12).
- **`MutationCache.onError`** maps status to curated copy from a new
  `src/lib/messages.ts` — a flat constants module, not an i18n framework.
- **`retry`** becomes a predicate: 5xx only.
- `staleTime`, `gcTime` and `refetchOnWindowFocus` keep their current values.

**Never echo server error text.** Status maps to curated copy. Server payloads may carry
stack traces or internal route names. Per-mutation `onError` is reserved for specific
handling — field-level errors, rollback — never a second generic toast.

---

## Guardrails and testing

**`scripts/check-contract.sh`**, in the style of `scripts/verify-infra.sh`: re-run the
export, re-run generation, fail on a non-empty `git diff`. Exposed as
`make check-contract` and invoked by `.github/workflows/api-contract.yml` — one script,
two callers. This is the repository's first CI workflow. It needs uv, pnpm and Node, and
no secrets.

**Server-side contract test** in `server/tests/unit/`, over `app.openapi()`: every
operation in the schema has an explicit `operation_id` (not FastAPI's auto-generated
`<func>_<path>_<method>` shape), an explicit tag, and either a response schema or 204.
This enforces the D-7 convention mechanically rather than by documentation, needs no
database, and is the piece most likely to survive the fork intact.

**No frontend tests.** The workspace has no test runner — no vitest, no jest, no
playwright, and the `msw: true` entry in `pnpm-workspace.yaml` is vestigial with nothing
depending on it. Introducing frontend test infrastructure is its own workstream, not a
rider on this one. The type checker, the contract check and the contract test are WS5's
verification.

---

## Acceptance

- `make export-openapi` followed by `pnpm --filter @app/api-client gen:api` leaves a
  clean `git diff`.
- `make check-contract` passes; the GitHub Actions workflow passes on a pull request.
- `pnpm -r exec tsc --noEmit` passes across the workspace.
- The server contract test passes.
- Both portal images build via `make docker-build-web`.
- The server-status widget renders from `useGetReadiness`, and no hand-written API
  request or response type remains anywhere under `web-app/`.
- No `useStreamChatMessage` exists in the generated output.
- `docs/api-client-codegen-setup.md` is updated to match every decision above, so the
  portable guide is correct for the B2C fork.

---

## Out of scope / follow-ups

| Item | Why deferred |
|---|---|
| Forms, `zodResolver`, the localized Zod error map (guide §8) | Zero forms exist. Localising a template that has not chosen a language is a decision WS5 should not make. The Zod target still ships, because §6.6's trust-boundary validation is what justifies it. |
| `apps/*/src/hooks/api/` wrapper layer (guide §7) | No mutations to wrap. Convention documented, directory not created. |
| Array-param serializer patch (guide §5, §9.2) | D-11. Add with the first `List[T] = Query(...)`. |
| Frontend test infrastructure | Its own workstream. |
| RSC prefetch / `HydrationBoundary` path | D-2's accepted trade-off. Add an explicit non-hook fetcher when first needed. |
| Import-time side effects in `app.main` | Belongs to whichever workstream touches startup. |
| SSE stream client | WS7. |
| Any new endpoint or UI | — |

---

## Risks accepted

**An orval upgrade changes committed output.** Mitigated by the exact pin (D-10) and by
`make check-contract`, which turns silent drift into a failing job. An upgrade is a
deliberate, reviewable commit.

**`operation_id` renames are breaking changes to frontend symbols.** Documented in
`server/CLAUDE.md` (D-7) and mechanically detectable: a rename produces a large generated
diff in the same commit.

**The hook mutator forecloses out-of-React calls.** Accepted under D-2 with a named
trigger to revisit.

**`process.env.NEXT_PUBLIC_API_URL` inside the package makes it Next-only.** Accepted:
every current and planned consumer is a Next.js application. Reversing it means passing
`baseUrl` through a provider, which reintroduces a provider.
