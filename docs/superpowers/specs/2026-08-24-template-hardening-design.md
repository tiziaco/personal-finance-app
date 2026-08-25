# Template Hardening — Design & Tracker

**Date:** 2026-08-24
**Status:** In progress
**Scope:** Five workstreams to bring the B2B template to a forkable state, ahead of a hard fork into a B2C (social network) project.

---

## Context

This repo is the B2B template (Rilevio: multi-tenant, Clerk Organizations, two portals). A B2C project — a social network with multiple roles, no organizations, single web app — will be created from it as a **hard fork**: copy the repo, strip orgs and the second portal, let the two diverge. No shared base package, no extraction layer.

That decision has one consequence that shapes everything below: **any fix worth having in both projects must land here, before the fork.** After the fork, the same fix costs twice.

All five workstreams sit in the part of the stack that is *not* organization-specific. None of them are B2B logic.

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
| 1 | Infrastructure reorganisation | ✅ Complete — 1 blocker outstanding | `plans/2026-08-24-ws1-infra-reorg.md` | — |
| 2 | Traefik in dev compose + Dokploy labels | Not started | — | — |
| 3 | Auth middleware hardening | Not started | — | Q1 (below) |
| 4 | Clerk webhooks + ngrok | Not started | — | — |
| 5 | Orval codegen | **Parked** | — | External config not yet available |
| 6 | Replace `starlette-prometheus` with in-house instrumentation | **Specified, not started** | — | Sequenced after WS1–WS5; **must precede** `uv lock --upgrade` |
| — | Fork to B2C | Not started | — | WS1–4 |

---

## WS1 — Infrastructure reorganisation

**Status:** ✅ Complete, with one acceptance criterion unmet — see Part 2 below.

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

### Part 2 — the outstanding blocker

Both web-app portal images currently **fail to build**:

```
Error: @clerk/clerk-react: The publishableKey passed to Clerk is invalid. (key="")
Export encountered an error on /_not-found/page
```

**Root cause:** `docker-compose.dev.yml` passes the key as a build arg,
`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: ${NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY:-""}`, resolved by compose
variable substitution from the root `.env`. It is not defined there, so the arg becomes the literal
two-character string `""`. The per-app `.env.local` does define it, but `env_file:` applies at
runtime only, and Next.js inlines `NEXT_PUBLIC_*` at build time, so a runtime value cannot substitute.

**Attribution (verified, not assumed):** `git show main:docker-compose.yml` carries the identical
`${NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY:-""}` line, and `git diff main..HEAD` shows this branch changed
no build args. The defect predates the branch. The working assessment — explicitly **not proven** —
is that Docker layer caching masked it until the package rename invalidated the cached
`RUN pnpm --filter $APP_NAME build` layer.

**Candidate fixes (open, none chosen — each is a secrets-handling decision for the user):**
1. Add the publishable key to root `.env` (it is a *publishable* key, designed to ship in client bundles).
2. Make the `/_not-found` route dynamic so no key is needed at build time.
3. Restructure how build args are sourced — cleanest, largest, arguably WS2's scope.

**Consequence:** WS1's acceptance criterion "`make docker-run` starts the stack" is currently unmet
for the two portals. The server image builds and runs healthy.

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

**F2 — `o.per` discarded.** `packages/auth/src/permissions.ts` exists on the frontend but the server checks roles only. **Fix:** extract permissions into `request.state`; add `require_permission()` alongside `require_role()`.

**F3 — No `azp` validation.** `verify_token` sets `verify_aud: False` and nothing checks the authorized party, so any valid token from the Clerk instance is accepted regardless of the origin that obtained it. **Fix:** validate `azp` against an allowlist of permitted origins. *This is the only finding here that is a security bug rather than a gap.*

**F4 — `BaseHTTPMiddleware` with an SSE endpoint.** `AuthMiddleware` extends `BaseHTTPMiddleware`; `server/app/api/v1/chatbot.py:140` returns a `StreamingResponse` with `text/event-stream`. `BaseHTTPMiddleware` pumps responses through an anyio memory stream — the known source of SSE buffering and mishandled client disconnects. **Fix:** convert to pure ASGI middleware.

**F5 — `org_id` nullability bug (adjacent, in the model).** `User.org_id` is `str`, non-nullable (`user.py:43`), but `anonymize_user` assigns `self.org_id = None` (`user.py:65`). The GDPR deletion path raises a NOT NULL violation on flush. The field must become nullable for B2C regardless. **Fix:** make nullable + Alembic migration.

**Acceptance:** unit tests cover v1 and v2 token shapes producing identical `request.state`; `azp` rejection is tested; SSE endpoint streams without buffering; `anonymize_user` round-trips against a real session.

---

## WS4 — Clerk webhooks + ngrok

**Problem:** No webhook handling. User records are created only by JIT provisioning in `get_current_user` → `user_provider.get_or_create_user`, so profile edits and deletions in Clerk never reach the database.

**Decision — webhooks are the source of truth; JIT is retained as a fallback.** Webhooks own profile updates and deletions. JIT stays because a dropped or delayed event would otherwise leave an authenticated user with no row. Removing JIT entirely trades a rare inconsistency for a hard failure.

**Decision — ngrok, not cloudflared.** Every ngrok account including the free tier gets one permanent static dev domain that survives agent restarts, so the endpoint URL in the Clerk dashboard is set once. Free-tier limits (1GB/month bandwidth, 3 concurrent endpoints) are far above webhook testing needs. Already in use on another project.

**Scope:**
- `svix` dependency; signature verification on the webhook endpoint.
- Handlers for `user.created`, `user.updated`, `user.deleted`, and the organization membership events.
- ngrok service in `docker-compose.dev.yml` bound to the static domain.

**Acceptance:** unsigned and replayed requests are rejected; a profile edit in the Clerk dashboard propagates to the database without a login; deleting a user triggers `anonymize_user` rather than a hard delete.

---

## WS5 — Orval codegen (parked)

**Problem:** API access is hand-written — `lib/api/health.ts` plus `hooks/use-server-status.ts` is currently the entire surface.

**Parked pending** the orval configuration from the user's other project. Matching that existing setup is worth more than inventing a second convention that would later have to be reconciled.

Migration cost is at its minimum right now (one hook), and no feature work is planned in this repo before the fork — so ordering it last costs nothing.

---

## WS6 — Replace `starlette-prometheus` with in-house instrumentation

**Status:** Specified, not started. **Sequenced after WS1–WS5.**

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

### Also outstanding

- `/api/v1/conversation/` returns 404 — a clean unmatched-route 404, not an exception. Route-shape question, unrelated to this defect.
- `packageManager` is unpinned in `web-app/package.json`; local pnpm is 11.21.0 while the container's corepack resolved 11.23.0. Same class of drift as the server lockfile bypass fixed in Task 3c.


## Open questions

**Q1 — Is the live Clerk instance emitting v1 or v2 session tokens?** *(blocks WS3)*
Decides whether F1's v1 branch is a live fix or defensive insurance. Does not change the shape of the fix, only its priority.

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
