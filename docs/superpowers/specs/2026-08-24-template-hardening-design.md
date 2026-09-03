# Template Hardening — Design & Tracker

**Date:** 2026-08-24
**Status:** In progress
**Scope:** Seven workstreams to bring the B2B template to a forkable state, ahead of a hard fork into a B2C (social network) project.

---

## Context

This repo is the B2B template (Rilevio: multi-tenant, Clerk Organizations, two portals). A B2C project — a social network with multiple roles, no organizations, single web app — will be created from it as a **hard fork**: copy the repo, strip orgs and the second portal, let the two diverge. No shared base package, no extraction layer.

That decision has one consequence that shapes everything below: **any fix worth having in both projects must land here, before the fork.** After the fork, the same fix costs twice.

All workstreams sit in the part of the stack that is *not* organization-specific. None of them are B2B logic.

### Current coupling surface (measured, not assumed)

Organization coupling is narrow — three places on the server, two on the frontend:

| Location | Coupling |
|---|---|
| `server/app/models/user.py:43` | `org_id: str` field |
| `server/app/api/middlewares/auth.py:43-45` | reads `o` claim from JWT |
| `server/app/api/dependencies/auth.py:57` | `get_current_role` reads `request.state.org_role` |
| `web-app/apps/*/src/proxy.ts` | role gate via `orgRole` |
| `web-app/packages/auth/src/permissions.ts` | `getUserRole(orgRole)` |

`get_current_role` is already documented in-code as "the backend portability seam". Keeping that seam narrow is a standing constraint on all work below — in B2C it becomes "read role from `publicMetadata`" and nothing else changes.

---

## Standing constraints

1. **Do not widen the role seam.** No service, repository, or endpoint may read `org_role` / `org_id` directly. Everything goes through `get_current_role` (server) and `getUserRole` (frontend).
2. **Genericise naming to `@app` / `app-network`.** `@rilevio/*` → `@app/*`, `rilevio-network` → `app-network`, and container names lose the product prefix. Chosen because it is neutral enough that the B2C fork needs no rename at all — fork cost for naming drops to zero.
   **Amended 2026-08-24 (user decision, WS1 Ruling 15):** the `@app` token applies to *workspace package scopes only*. The two ROOT packages take their directory's name instead — `web-app/package.json` is `web-app`, `server/pyproject.toml` is `server`. One rule: package name equals directory name. Both are private and unpublished, so the name is a local label with no resolution or collision consequences. The originally-planned `app-web` / `app-server` applied the token to two names that were already neutral, buying nothing and reading worse than the directory they name.
3. **Version control before file moves.** ✅ Done — repo initialised on `main`, baseline commit `296c3b7`. Existing `.gitignore` files (root, `server/`, `web-app/`) were verified to cover every secret file and left unmodified.

---

## Workstream tracker

| # | Workstream | Status | Plan | Blocked by |
|---|---|---|---|---|
| 1 | Infrastructure reorganisation | ✅ Complete | `plans/2026-08-24-ws1-infra-reorg.md` | — |
| 2 | Traefik in dev compose + Dokploy labels | Not started | — | — |
| 3 | Auth middleware hardening | ✅ F3, F5 shipped; F1, F2 descoped; F4 superseded by WS7 | — | Q1 (below, resolved) |
| 4 | Clerk webhooks + ngrok | ✅ Complete | `plans/2026-08-26-ws4-clerk-webhooks.md` | — |
| 5 | Orval codegen | ✅ Complete | `plans/2026-09-01-ws5-api-client-codegen.md` | — |
| 6 | Replace `starlette-prometheus` with in-house instrumentation | ✅ Complete, as **Option B** not A — see [As built](#as-built-2026-09-03) | — | — |
| 7 | SSE stream disconnect handling | Not started | — | — |
| — | Fork to B2C | Not started | — | WS1–4 |

---

## WS1 — Infrastructure reorganisation

**Status:** ✅ Complete. The build blocker recorded in Part 2 was fixed in `2c0a0de` (on `main`
via `fix/ws1-docker-hardening`); that section is kept as the record of the defect and its
resolution.

**Problem:** `prometheus/` and `grafana/` sit in the repo root alongside application code. `docker-compose.yml` mixes dev concerns with a name that implies it is the default for all environments.

**Scope:**
- Move `prometheus/` and `grafana/` under a single `infra/` directory.
- Rename `docker-compose.yml` → `docker-compose.dev.yml`; update `Makefile` targets and any `scripts/*.sh` references.
- Genericise the package scope (`@rilevio/*` → single token), network name (`rilevio-network`), root package names (→ directory-matching `web-app` / `server`), and `container_name` entries.

**Acceptance:** `make docker-run` and `make docker-run-core` start the full and core stacks unchanged; Grafana still finds its datasource and dashboards; no stale path references remain anywhere in `Makefile`, compose files, or `server/scripts/`.

**Rationale for going first:** it moves files. Every later workstream adds services or edits compose; doing the move afterwards means redoing that work.

### Part 1 — what shipped

- `prometheus/` and `grafana/` moved under `infra/`; compose bind mounts repointed.
- `docker-compose.yml` renamed to `docker-compose.dev.yml`; `Makefile` parameterised with `COMPOSE_FILE` threaded through all 10 compose call sites; two dead `personal-finance-app-*` image names removed from `clean`.
- Docker network unified as `app-network` across dev and prod (they had drifted to `rilevio-network` and `app`).
- pnpm scope `@rilevio/*` renamed to `@app/*` across 33 files; root packages renamed to directory-matching names `web-app` and `server`.
- Documentation updated to the new layout and identifiers.
- `scripts/verify-infra.sh` created; reports `SUMMARY: 19 passed, 0 failed, 0 skipped (19 checks)`.
- Two build repairs made along the way that were not in the original plan: the web-app image could not build at all (pnpm `allowBuilds` plus missing root manifests in the builder stage), and the server image built irreproducibly (it ignored `uv.lock` and ran Python 3.12 against a 3.13 project). Both are fixed; the server container now reports `healthy`, which it had never done before.

### Part 2 — the blocker (resolved)

**Resolved in `2c0a0de`** ("enforce required Clerk publishable key in build args"), which took
candidate fix 3 below — restructuring how the arg is sourced. Two halves:

- `docker-compose.dev.yml:12,31` now use compose's required-variable form,
  `${NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY:?required at build time …}`, so an absent key fails the
  build with a named error instead of substituting the literal `""` that caused the original
  failure.
- `Makefile:16-18` adds `-include web-app/apps/internal-portal/.env.local` ahead of
  `.EXPORT_ALL_VARIABLES:`, so the key the portals already define reaches compose's substitution
  environment. Note the asymmetry: **both** images build with the *internal* portal's key,
  because only that file is included. Identical in both `.env.local` files today; it would need
  revisiting if the portals ever point at different Clerk instances.

WS1's acceptance criterion "`make docker-run` starts the stack" is therefore met.

#### Historical record — the defect as diagnosed on 2026-08-24

Nothing below describes current behaviour; it is kept for the attribution, which took real work
to establish.

Both web-app portal images **failed to build**:

```
Error: @clerk/clerk-react: The publishableKey passed to Clerk is invalid. (key="")
Export encountered an error on /_not-found/page
```

**Root cause:** `docker-compose.dev.yml` passed the key as a build arg,
`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: ${NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY:-""}`, resolved by compose
variable substitution from the root `.env`. It was not defined there, so the arg became the literal
two-character string `""`. The per-app `.env.local` did define it, but `env_file:` applies at
runtime only, and Next.js inlines `NEXT_PUBLIC_*` at build time, so a runtime value could not
substitute.

**Attribution (verified, not assumed):** `git show main:docker-compose.yml` carried the identical
`${NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY:-""}` line, and `git diff main..HEAD` showed the WS1 branch
changed no build args. The defect predated the branch that surfaced it. The working assessment —
explicitly **not proven** — was that Docker layer caching masked it until the package rename
invalidated the cached `RUN pnpm --filter $APP_NAME build` layer.

**Candidate fixes considered at the time (3 is the one taken):**
1. Add the publishable key to root `.env` (it is a *publishable* key, designed to ship in client bundles).
2. Make the `/_not-found` route dynamic so no key is needed at build time.
3. Restructure how build args are sourced — cleanest, largest, arguably WS2's scope.

### Also deferred (each already known, none are WS1 defects)

- `docker-compose.prod.yml` is stale and unparseable by `docker compose config` — it declares a single `web-app` service whose `env_file` points at a nonexistent path. Deferred to WS2.
- `web-app/package.json` does not pin `packageManager`; local pnpm and the container's corepack resolved different versions.
- `web-app/packages/types` has no `tsconfig.json`, so the root `pnpm type-check` (`pnpm -r exec tsc --noEmit`) cannot check all packages. Pre-existing since the initial commit.
- `/api/v1/conversation/` returns 404 — a clean unmatched route, not an exception.
- Host port 5432 in `docker-compose.dev.yml` collides with another project the user runs; worth making configurable.

---

## WS2 — Traefik in dev compose + Dokploy labels

**Problem:** Deployment targets Dokploy, which routes via Traefik. `docker-compose.prod.yml` currently publishes `3000:3000` and `8000:8000` to the host — wrong shape for a Traefik-fronted deploy, and untested locally.

**Decision — hand-written labels, not the Dokploy UI.** Dokploy supports two mutually exclusive approaches: native domain configuration through the UI Domains tab (Dokploy injects labels), or hand-written Traefik labels in the compose file. Mixing them produces two competing router definitions for the same service. Since the goal is to *test the routing setup locally*, hand-written labels are the only option that can be exercised outside Dokploy — so the deploy side must also use the manual approach, and the Domains tab is left alone.

**Scope:**
- Add a Traefik service to `docker-compose.dev.yml` so the labels can be exercised locally.
- Replace host port bindings in `docker-compose.prod.yml` with `expose` + Traefik labels.
- Verify the labels resolve correctly against the local Traefik before they reach Dokploy.
- **Repair prod compose staleness (inherited from WS1).** `docker-compose.prod.yml` does not currently parse: it declares a single `web-app` service pointing `env_file` at `./web-app/.env.local`, a path that has never existed. Prod compose predates the two-portal split — dev has `internal-portal` and `supplier-portal`, each with its own `apps/*/.env.local`. WS1 deliberately left this alone because fixing it means deciding the prod service topology, which is this workstream's call. Until it is fixed, `docker compose -f docker-compose.prod.yml config` fails and prod can only be validated structurally.

**Acceptance:** portals and API are reachable through local Traefik by hostname, not by published port; `docker-compose.prod.yml` publishes no application ports to the host.

**Rejected:** a Traefik container in the *production* compose file. Dokploy runs its own Traefik; a second one would contend for ports 80/443.

---

## WS3 — Auth middleware hardening

**Status:** F3 and F5 shipped (`feat/ws3-auth-hardening`, commits `7f813ff`/`ff12417` for F3). F1 and F2 descoped — user decision, 2026-08-25 (see below). F4 superseded by [WS7](#ws7--sse-stream-disconnect-handling) — the fix landing there is not the one originally proposed here.

**Problem:** `server/app/api/middlewares/auth.py` handles only Clerk session token v2, discards most of the token, and performs no authorized-party validation.

Note the drift: `docs/superpowers/specs/2026-04-11-clerk-rbac-design.md` documents the claims as `org_id` / `org_role` (**v1** shape), while the middleware reads `o.id` / `o.rol` (**v2** shape). One of the two is wrong about the live instance.

### Findings

**F1 — No v1 fallback; failure is silent and total.**
`payload.get("o") or {}` yields `{}` under a v1 token, so `org_id` and `org_role` are both `None`, so `get_current_role` raises `AuthorizationError` on every guarded endpoint. Claim shapes differ in both name and value:

| | v1 | v2 |
|---|---|---|
| org id | `org_id` | `o.id` |
| org slug | `org_slug` | `o.slg` |
| role | `org_role` (**with** `org:` prefix) | `o.rol` (**no** prefix) |
| permissions | `org_permissions` (prefixed) | `o.per` |

The middleware docstring claims it strips the `org:` prefix. It does not strip anything — correct for v2, wrong for v1. **Fix:** branch on the `v` claim, normalise both shapes into identical `request.state` values.

**Descoped — user decision, 2026-08-25.** No v1 fallback needed; Q1 (below) resolved the live instance as v2-only, and there is no plan to support a v1 deployment.

**F2 — `o.per` discarded.** `packages/auth/src/permissions.ts` exists on the frontend but the server checks roles only. **Fix:** extract permissions into `request.state`; add `require_permission()` alongside `require_role()`.

**Descoped — user decision, 2026-08-25.** No permission management scheme exists yet; adding `require_permission()` ahead of that would be speculative.

**F3 — No `azp` validation.** `verify_token` sets `verify_aud: False` and nothing checks the authorized party, so any valid token from the Clerk instance is accepted regardless of the origin that obtained it. **Fix:** validate `azp` against an allowlist of permitted origins. *This is the only finding here that is a security bug rather than a gap.*

**✅ Shipped.** `ClerkJWTVerifier.verify_token()` now accepts either `azp ∈ settings.cors.ALLOWED_ORIGINS` (session tokens from the frontend `getToken()` flow) or `client_id == settings.auth.OAUTH_CLIENT_ID` (Swagger's `/docs` OAuth 2.0 + PKCE flow, which carries no `azp` at all — a structurally different Clerk token type, discovered via live testing, not assumed upfront). No new config — reuses the two settings already populated for CORS and Swagger's OAuth init. Commits `7f813ff` (implementation) / `ff12417` (tests) on `feat/ws3-auth-hardening`.

**F4 — `BaseHTTPMiddleware` with an SSE endpoint.** `AuthMiddleware` extends `BaseHTTPMiddleware`; `server/app/api/v1/chatbot.py:140` returns a `StreamingResponse` with `text/event-stream`. `BaseHTTPMiddleware` pumps responses through an anyio memory stream — the known source of SSE buffering and mishandled client disconnects. **Fix (originally proposed):** convert to pure ASGI middleware.

**Superseded by WS7 — user decision, 2026-08-25: keep `BaseHTTPMiddleware`.** Converting `AuthMiddleware` alone would have been a partial fix regardless — `LoggingContextMiddleware`, `SecurityHeadersMiddleware`, and `MetricsMiddleware` are also `BaseHTTPMiddleware` and each adds its own anyio-stream hop around the SSE response; a real fix would mean rewriting all four as pure ASGI. More directly: the actual risk in this codebase is that `chatbot.py`'s `event_generator()` never checks for client disconnect, so a client leaving mid-stream doesn't stop the LLM call — that gap exists independent of the middleware base class. [WS7](#ws7--sse-stream-disconnect-handling) fixes that gap directly instead.

**F5 — `org_id` nullability bug (adjacent, in the model).** `User.org_id` is `str`, non-nullable (`user.py:43`), but `anonymize_user` assigns `self.org_id = None` (`user.py:65`). The GDPR deletion path raises a NOT NULL violation on flush. The field must become nullable for B2C regardless. **Fix:** make nullable + Alembic migration.

**✅ Shipped** (prior to this tracker update). `User.org_id` is `Optional[str]` (`app/models/user.py:46`).

**Acceptance (as scoped after descoping/superseding above):** unit tests cover `azp`/`client_id` token-party validation (done, 13 tests in `test_auth_utils.py`); `anonymize_user` round-trips against a real session (done, F5). SSE streaming without buffering is no longer this workstream's acceptance criterion — see WS7.

---

## WS4 — Clerk webhooks + ngrok

**Status:** ✅ Complete (`feat/ws4-clerk-webhooks`). All three acceptance criteria met: unsigned
and replayed requests rejected, and erasure anonymising rather than hard-deleting, are both
covered end to end in `server/tests/integration/api/test_webhooks.py`; dashboard-edit propagation
without a login was verified manually against the live tunnel on 2026-08-28.

Design decisions taken during implementation are in
`plans/2026-08-26-ws4-execution-rulings.md` (28 rulings) and
`specs/2026-08-26-ws4-clerk-webhooks-design.md`. One amendment to the decision below: webhooks
own profile updates and deletions as planned, but they are **not** the authority on user
*creation* — a webhook payload is a past-tense statement, and svix redelivers after a deletion,
so both create paths confirm against the Clerk API before inserting a row. See
`app/integrations/clerk/webhooks/handlers/` and `UserService.exists_in_clerk`.

Carried forward, both by decision rather than oversight: no reconciliation job against the Clerk
API (webhooks that are never delivered go unnoticed), and the `ngrok` compose service is
unguarded by a profile, so `make docker-run` requires ngrok credentials.

**Problem:** No webhook handling. User records are created only by JIT provisioning in `get_current_user` → `user_provider.get_or_create_user`, so profile edits and deletions in Clerk never reach the database.

**Decision — webhooks are the source of truth; JIT is retained as a fallback.** Webhooks own profile updates and deletions. JIT stays because a dropped or delayed event would otherwise leave an authenticated user with no row. Removing JIT entirely trades a rare inconsistency for a hard failure.

**Decision — ngrok, not cloudflared.** Every ngrok account including the free tier gets one permanent static dev domain that survives agent restarts, so the endpoint URL in the Clerk dashboard is set once. Free-tier limits (1GB/month bandwidth, 3 concurrent endpoints) are far above webhook testing needs. Already in use on another project.

**Scope:**
- `svix` dependency; signature verification on the webhook endpoint.
- Handlers for `user.created`, `user.updated`, `user.deleted`, and the organization membership events.
- ngrok service in `docker-compose.dev.yml` bound to the static domain.

**Acceptance:** unsigned and replayed requests are rejected; a profile edit in the Clerk dashboard propagates to the database without a login; deleting a user triggers `anonymize_user` rather than a hard delete.

---

## WS5 — Orval codegen

**Superseded by `specs/2026-09-01-ws5-api-client-codegen-design.md`.** Unparked on
2026-09-01: the orval configuration from the other project arrived as
`docs/api-client-codegen-setup.md`, was reviewed against this repo, and the WS5 design
now records where it holds and where it does not.

**Problem:** API access is hand-written — `lib/api/health.ts` plus `hooks/use-server-status.ts` is currently the entire surface.

Migration cost is at its minimum right now (one hook), and no feature work is planned in this repo before the fork — so ordering it last costs nothing.

---

## WS6 — Replace `starlette-prometheus` with in-house instrumentation

**Status:** ✅ Complete on `refactor/ws6-in-house-metrics` — but **built as Option B, not the Option A specified below**. The decision record in this section is what was planned; [As built](#as-built-2026-09-03) is what shipped and why. Read both before forking.

### Part 1 — root cause, already fixed in WS1 (Task 3c, commit `75af7a9`)

`/health`, `/ready`, `/`, and every `/api/v1/*` route returned 500. The cause was not application code: `server/Dockerfile` never copied `uv.lock` and ran `uv pip compile pyproject.toml`, re-resolving on every build against unbounded lower bounds (`fastapi>=0.121.0`). The image therefore installed **fastapi 0.141.1 / starlette 1.6.0** against a lockfile pinning **0.129.0 / 0.52.1**, on **Python 3.12** despite `requires-python = ">=3.13"`.

FastAPI 0.141 added `fastapi.routing._IncludedRouter`; `app.include_router()` now places that wrapper in `app.routes` rather than flattening child routes. `starlette-prometheus` 0.10.0's `get_path_template()` iterates `request.app.routes` and reads `route.path`, which the wrapper does not expose — so every included-router route raised `AttributeError` inside the middleware, before the handler ran.

Task 3c changed four Dockerfile lines (copy `uv.lock`, `uv export --frozen`, `python:3.13-slim` on both stages, pinned `uv` binary) and touched no server code. Verified after: Python 3.13.15, fastapi 0.129.0, starlette 0.52.1, `_IncludedRouter` absent, `/` 200, `/health` 200, `/ready` 401 (auth required — correct), `/api/v1/auth/me` 401, zero `AttributeError` in logs, and the `server` container reporting `healthy` for the first time.

### Part 2 — the deferred decision this workstream exists to make

The 500s are gone **only because FastAPI is now pinned below 0.141**. The incompatibility is untouched. The planned dependency-version bump reintroduces it exactly.

**⛔ Ordering constraint: this workstream MUST complete before `uv lock --upgrade`.** Bumping first reintroduces the 500s and entangles two unrelated changes.

### Decision: Option A — remove the package, own the instrumentation

**Evidence that decided it.** Every PromQL expression across all three dashboards in `infra/grafana/dashboards/json/` was extracted. They query `http_requests_total`, `llm_inference_duration_seconds`, `llm_stream_duration_seconds` (all in-house, from `server/app/core/metrics.py`) and cAdvisor's `container_*`. **Zero reference any `starlette_*` metric.** One panel filters on `endpoint!~"/metrics|/health"` — `endpoint` is the in-house label name; `starlette-prometheus` uses `path_template`. The dashboards were built against the in-house middleware throughout.

So the package collects and ships five metric families that nothing displays, while duplicating the request-count and duration the in-house middleware already records.

**Options considered:**

| | Change | Why not chosen |
|---|---|---|
| **A — chosen** | Drop the package; keep and improve `MetricsMiddleware` | — |
| B | Drop both middlewares; adopt `prometheus-fastapi-instrumentator` | Actively maintained and a genuine contender, but reintroduces the same coupling class that just caused this outage: a third-party package tracking FastAPI internals. Rejected for a template that will be forked, not for technical inadequacy. |
| C | Keep the package; pin `fastapi<0.141` | Lets a dependency with a ~2-year release cadence dictate the framework version. This is the current implicit state via the lockfile — a deferral, not a decision. |

**Package facts behind the choice:** `starlette-prometheus` is third-party (by PeRDy), not an Encode or FastAPI project. Latest release 0.10.0, September 2024; prior release January 2022. Not abandoned, but slow enough that a FastAPI-internals break can sit unfixed for a long time — as it has here.

**Why A specifically suits this repo:** the dashboards already plot in-house metrics exclusively. The B2C fork inherits those dashboards, and Option A means everything they plot comes from code in this repo, with no third-party package able to break them on a framework bump.

### Scope

**1. Rewrite `server/app/api/middlewares/prometheus.py`** — keep the `/metrics` route, drop the middleware:

```python
"""Prometheus metrics endpoint."""

from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, generate_latest
from starlette.requests import Request
from starlette.responses import Response


def metrics(request: Request) -> Response:
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)


def setup_metrics(app) -> None:
    """Expose Prometheus metrics at /metrics."""
    app.add_route("/metrics", metrics)
```

The in-house counters in `server/app/core/metrics.py` register into `prometheus_client`'s default `REGISTRY`, which is what the replaced library route read — so the endpoint keeps serving them unchanged. The library's multiprocess branch is dropped deliberately: it activates only when `prometheus_multiproc_dir` is set, which requires multiple workers, and the container runs single-process uvicorn.

**2. Fix label cardinality in `server/app/api/middlewares/metrics.py`.** It currently labels `endpoint` with `request.url.path` — the raw path. Every distinct UUID becomes a new Prometheus time series. This is the one real capability `starlette-prometheus` had that the in-house middleware lacks, and it must not be lost in the swap:

```python
route = request.scope.get("route")
endpoint = getattr(route, "path", request.url.path)  # template when matched, raw as fallback
```

This matters disproportionately for the B2C project, whose per-user and per-post routes would otherwise explode cardinality.

**3. Add the two metrics worth keeping** from the removed package — an exceptions counter by exception type, and an in-flight requests gauge — to `server/app/core/metrics.py`, using in-house names consistent with `http_requests_total`.

**4. Remove `starlette-prometheus>=0.7.0`** from `server/pyproject.toml`; re-lock with `uv lock` (**not** `--upgrade`).

### Acceptance

- `/metrics` returns 200 and Prometheus text format; `http_requests_total`, `llm_inference_duration_seconds`, `llm_stream_duration_seconds` all still present.
- No `starlette_*` series remain.
- `endpoint` labels show route templates (`/api/v1/conversation/{id}`), not concrete paths.
- Prometheus `/api/v1/targets` shows the `fastapi` job `up`.
- All three Grafana dashboards render with data.
- `grep -r starlette_prometheus server/` returns nothing.
- `uv lock --check` exits 0.
- Only then: `uv lock --upgrade` and the `uv add --bounds` pass.

### As built (2026-09-03)

**Option B was chosen during implementation, reversing the decision above.**
`628c7ba` deleted `app/api/middlewares/metrics.py` and adopted
`prometheus-fastapi-instrumentator`. The rejection of B rested on "a third-party
package tracking FastAPI internals", which conflated two different couplings:
`starlette-prometheus` broke because `get_path_template()` walks `app.routes`
and reads `route.path`, reimplementing route resolution. The instrumentator
reads `scope["route"]`, which is ASGI-level state FastAPI populates for anyone —
the same lookup Option A's own scope item 2 prescribed. Owning ~40 lines of
middleware to reach the identical scope key was cost without insulation.

`app/api/middlewares/prometheus.py` carries the non-default settings that keep
the dashboards' label contract, each with the reason it is not the library
default; `tests/unit/middleware/test_metrics_setup.py` pins that contract so a
dependency bump cannot silently blank a panel — which is the protection Option A
was actually after.

**Scope item 2** landed as specified in effect but not in name: the label is
`handler`, the library's name, not `endpoint`. All dashboard queries were
migrated. The acceptance criterion below still says `endpoint`; read it as
satisfied.

**Scope item 3 is half delivered, half descoped.**

- The exceptions counter shipped in `510d425` as
  `app_exceptions_total{error_code, exception_type}`, incremented in
  `service_exception_handler` and `global_exception_handler`, with a
  "Failures by Cause" panel on `API Overview`. It is labelled by the existing
  `ServiceError.error_code` taxonomy rather than by exception type alone — the
  five LLM failure modes all carry status 503, so the code is what tells them
  apart.
- **The in-flight gauge was dropped** — user decision, 2026-09-03, on value.
  Worth recording for anyone who tries to add it later:
  `should_instrument_requests_inprogress=True` is not a one-line change.
  In `prometheus_fastapi_instrumentator` 8.x, `middleware.py` builds that gauge
  without passing `registry=`, unlike every other metric it creates, so it
  always lands on the global default `REGISTRY`. `setup_metrics(app, registry=…)`
  exists precisely so each test gets clean series, and the metrics tests build a
  fresh app per test — the second one raises
  `DuplicateTimeseries: {'http_requests_inprogress'}`. Reproduced. An in-house
  gauge plus a small ASGI middleware is the way in, not the flag.

**Acceptance, verified 2026-09-03 against the running dev stack:** `/metrics`
200 with all families present; zero `starlette_*` series; labels are route
templates; the `fastapi` Prometheus job `up`; `uv lock --check` clean;
`grep -r starlette_prometheus server/` finds only a docstring and a test name.
The ordering constraint held — `628c7ba` precedes the bulk upgrade in `812fdf2`.

One criterion does **not** pass: *"All three Grafana dashboards render with
data."* `Infrastructure` returns zero series on every panel. Not caused by this
workstream — cAdvisor exposes only the root cgroup (`id="/"`) with no `name`,
`image` or `container_label_*` labels at all, so the panels' grouping by
`container_label_com_docker_compose_service` matches nothing. Cause is
`--docker_only=true` against Docker Desktop on Darwin, where the mounted `/sys`
and `/var/lib/docker` belong to the LinuxKit VM rather than to the daemon's
container cgroups. Expected to work on a Linux host; unverified there.

### Also outstanding

- `/api/v1/conversation/` returns 404 — a clean unmatched-route 404, not an exception. Route-shape question, unrelated to this defect.
- `packageManager` is unpinned in `web-app/package.json`; local pnpm is 11.21.0 while the container's corepack resolved 11.23.0. Same class of drift as the server lockfile bypass fixed in Task 3c.


## WS7 — SSE stream disconnect handling

**Status:** Not started. Grew out of WS3/F4 — see that finding for the middleware analysis that led here.

**Problem:** `server/app/api/v1/chatbot.py`'s `event_generator()` (used by the `StreamingResponse(..., media_type="text/event-stream")` chat endpoint) never checks whether the client is still connected. If a client navigates away or drops the connection mid-stream, nothing stops the loop — it keeps calling `agent.get_stream_response()` and consuming LLM output for a listener that no longer exists, burning tokens and time for nothing.

**Decision — keep `BaseHTTPMiddleware`; do not rewrite the middleware stack.** WS3/F4 originally proposed converting `AuthMiddleware` to pure ASGI. Rejected:
- Every `BaseHTTPMiddleware` in the stack (`AuthMiddleware`, `LoggingContextMiddleware`, `SecurityHeadersMiddleware`, `MetricsMiddleware`) contributes its own anyio-stream hop around a streamed response — converting only `AuthMiddleware` would not have removed the indirection, only reduced it by one layer of four.
- The disconnect-propagation bug historically associated with `BaseHTTPMiddleware` was substantially fixed upstream; this repo runs a recent Starlette (`0.52.1`, checked against PyPI's latest `1.6.0` — this repo is behind current but not on an old, bug-era release).
- The actual gap — `event_generator()` never checking for disconnect — exists regardless of the middleware base class. Fixing the middleware layer would not have fixed it.

**Decision — `sse-starlette`, not a hand-rolled disconnect check.** `sse-starlette`'s `EventSourceResponse` checks `request.is_disconnected()` internally and stops the generator when the client leaves, plus handles ping/keepalive framing — a purpose-built replacement for the raw `StreamingResponse` currently used, rather than reimplementing disconnect polling by hand.

**Scope:**
- Add `sse-starlette` dependency to `server/pyproject.toml`.
- Replace `StreamingResponse(event_generator(), media_type="text/event-stream")` in `chatbot.py` with `EventSourceResponse(event_generator())`.
- Confirm `event_generator()`'s existing `data: {json}\n\n` formatting is compatible with (or adapted to) `sse-starlette`'s event yielding convention.

**Acceptance:** a client disconnecting mid-stream stops the underlying LLM call/loop promptly (not after full completion); normal (non-disconnected) streaming behavior and event shape are unchanged for existing consumers; no regression in `AuthMiddleware`/`AccessLogMiddleware`/etc. behavior on this route.

---

## Open questions

**Q1 — Is the live Clerk instance emitting v1 or v2 session tokens?** *(blocked WS3, now resolved)*
Decides whether F1's v1 branch is a live fix or defensive insurance. Does not change the shape of the fix, only its priority.

**Resolved 2026-08-25:** confirmed **v2** — a real decoded session token from the browser during WS3/F3 work carries `"v": 2` and the `o.{id,rol,slg}` claim shape. Moot in practice now that F1 is descoped, but recorded for the record.

---

## Decision log

| Decision | Rationale |
|---|---|
| Hard fork, not shared base | Two repos allowed to diverge; no abstraction cost paid up front. Accepts that a future fix lands twice. |
| Fixes land here, before the fork | All five workstreams are in non-org-specific code; B2C inherits them for free. |
| Hand-written Traefik labels on both sides | Only approach testable outside Dokploy; mixing with the UI Domains tab creates competing routers. |
| Webhooks as source of truth, JIT retained | Dropped events degrade to staleness instead of hard auth failure. |
| ngrok over cloudflared | Free static domain is permanent; already in use elsewhere. |
| Orval last | Config unavailable; no feature work blocked by its absence. |
| Naming token `@app` / `app-network` | Neutral enough that the B2C fork inherits the names unchanged — no post-fork rename. |
| Keep existing `.gitignore` files | Already cover all secrets (root `.env`, `server/.env.*`, `web-app` `.env*` with `!.env.example`); verified against the staged set before the baseline commit. |
| WS3/F1, F2 descoped | No v1 Clerk deployment planned (Q1 resolved v2-only); no permission scheme exists yet to hang `require_permission()` off of. |
| WS3/F4 superseded by WS7 | Converting `AuthMiddleware` alone was a partial fix (3 other `BaseHTTPMiddleware` classes remain in the stack) and didn't address the actual gap — `chatbot.py`'s stream generator never checks for client disconnect. |
| WS7: `sse-starlette` over ASGI middleware rewrite | User decision: keep `BaseHTTPMiddleware`. Fixes the real disconnect gap directly at the response layer instead of rewriting four middleware classes for a smaller, more diffuse benefit. |
| WS6 built as Option B, reversing the spec | The rejection of B assumed the same coupling that broke `starlette-prometheus`. It walked `app.routes` reimplementing route resolution; the instrumentator reads `scope["route"]`, the same ASGI key Option A's own scope prescribed. A pinned label contract in tests gives the insulation that owning the middleware was meant to buy. |
| WS6 in-flight gauge descoped | User decision, 2026-09-03: low value. Also not free — the library registers that one gauge on the default registry regardless of `registry=`, breaking test isolation; it would need an in-house gauge and middleware. |
