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
2. **Genericise naming.** `@rilevio/*`, `rilevio-network`, and hardcoded container names become a single replaceable token, so the fork is one search-replace rather than a hunt.
3. **Version control before file moves.** `git init` this repo before WS1 executes.

---

## Workstream tracker

| # | Workstream | Status | Plan | Blocked by |
|---|---|---|---|---|
| 1 | Infrastructure reorganisation | Not started | — | `git init` |
| 2 | Traefik in dev compose + Dokploy labels | Not started | — | WS1 |
| 3 | Auth middleware hardening | Not started | — | Q1 (below) |
| 4 | Clerk webhooks + ngrok | Not started | — | WS1 |
| 5 | Orval codegen | **Parked** | — | External config not yet available |
| — | Fork to B2C | Not started | — | WS1–4 |

---

## WS1 — Infrastructure reorganisation

**Problem:** `prometheus/` and `grafana/` sit in the repo root alongside application code. `docker-compose.yml` mixes dev concerns with a name that implies it is the default for all environments.

**Scope:**
- Move `prometheus/` and `grafana/` under a single `infra/` directory.
- Rename `docker-compose.yml` → `docker-compose.dev.yml`; update `Makefile` targets and any `scripts/*.sh` references.
- Genericise the package scope (`@rilevio/*` → single token), network name (`rilevio-network`), and `container_name` entries.

**Acceptance:** `make docker-run` and `make docker-run-core` start the full and core stacks unchanged; Grafana still finds its datasource and dashboards; no stale path references remain anywhere in `Makefile`, compose files, or `server/scripts/`.

**Rationale for going first:** it moves files. Every later workstream adds services or edits compose; doing the move afterwards means redoing that work.

---

## WS2 — Traefik in dev compose + Dokploy labels

**Problem:** Deployment targets Dokploy, which routes via Traefik. `docker-compose.prod.yml` currently publishes `3000:3000` and `8000:8000` to the host — wrong shape for a Traefik-fronted deploy, and untested locally.

**Decision — hand-written labels, not the Dokploy UI.** Dokploy supports two mutually exclusive approaches: native domain configuration through the UI Domains tab (Dokploy injects labels), or hand-written Traefik labels in the compose file. Mixing them produces two competing router definitions for the same service. Since the goal is to *test the routing setup locally*, hand-written labels are the only option that can be exercised outside Dokploy — so the deploy side must also use the manual approach, and the Domains tab is left alone.

**Scope:**
- Add a Traefik service to `docker-compose.dev.yml` so the labels can be exercised locally.
- Replace host port bindings in `docker-compose.prod.yml` with `expose` + Traefik labels.
- Verify the labels resolve correctly against the local Traefik before they reach Dokploy.

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
