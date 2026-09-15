# B2C Hard Fork — Design

**Date:** 2026-09-15
**Status:** Approved, not started
**Source:** this repo at `cfca621`
**Target:** `/Users/tizianoiacovelli/projects/fullstack-b2c-nextjs-fastapi-template`
(empty, `origin` = `git@github-personal:tiziaco/fullstack-b2c-nextjs-fastapi-template.git`)

**This document lives in the source repo and stays there.** Step 9 deletes
`docs/superpowers/` *in the target*; this spec is the B2B repo's record of how the
fork was performed, and is read from the source checkout during execution. Nothing
carries it across.

Executes the fork that [`2026-08-24-template-hardening-design.md`](./2026-08-24-template-hardening-design.md)
was written to unblock. WS1–WS6 shipped; WS7 stays deferred by standing decision.

---

## What the target is

**A reusable B2C template**, not the social-network product. Orgs removed, one web app,
no example business domain. The social network becomes a later fork *of this new template*.

That framing decides most of what follows: anything speculative is out, including an
example domain and an admin console shell.

## Coupling surface (measured at `cfca621`, not assumed)

The hardening spec's table listed five org touchpoints. That was accurate for *organizations*
and misleading for the fork, because the B2B **domain** is far wider than the org seam:

| | Files | Notes |
|---|---|---|
| `org_id` / `org_role` / `organization` | 11 server, 11 web | The narrow seam the spec described |
| `supplier` | 31 server files | `services/user/service.py` (42 refs), `cache.py` (21), a dedicated `supplier_repository.py`, `membership.py`, `authentication.py` |
| AI stack | ~1,530 of 7,047 server LOC | `agents/`, `services/llm`, `services/conversation` |

`UserService` exposes 8 public methods: 3 supplier-specific, 1 org-specific, 4 keepers.
`authorization.py` exposes 4 named role guards, all B2B, over one reusable `require_role` factory.

The work is therefore mostly deletion with one real substitution.

---

## Decisions

| Decision | Rationale |
|---|---|
| Reusable B2C template, not the product | The social network forks from it later. Keeps the template free of domain assumptions. |
| No example domain — `User` + `Conversation` only | `Supplier` is stripped outright, nothing replaces it. Nothing to delete on the next fork. |
| Role from Clerk `publicMetadata.role`, **one copy** | A DB mirror was considered and rejected — see below. |
| Roles are `user` / `admin` | Minimum that still exercises `require_role()` non-trivially. |
| Keep the AI stack | Template stays AI-capable out of the box. Inherits WS7. |
| Squashed initial commit | Provenance recorded in the message; `git log` reflects B2C work only. |
| Drop `docs/superpowers/` | A B2C template should not ship a dozen documents about supplier compliance. Referencing docs are rewritten, not left dangling. |
| One app at `web-app/apps/web`; keep `apps/` | Costs one directory level; collapsing rewrites both Dockerfiles, both compose files, `APP_NAME`, `deploy-check` and several Makefile targets — twice, if an admin app ever arrives. |
| Strip-in-place, not build-up-from-empty | The template's value *is* the machinery that already works. Building up puts all of it at risk to avoid leftovers a `git grep` sweep catches for free. |

### Why the role is not mirrored to the database

`proxy.ts:18` gates routes in Next.js edge middleware from session claims alone — no database
reach. So the role must ride the token regardless; the only question was whether to *also*
keep a `User.role` column for SQL queries.

Rejected, on a specific ground. The column would have replaced the existing Clerk-API fallback
in `get_current_role`, which is cached 60s and therefore **self-healing**. The hardening spec
records that there is no reconciliation job against the Clerk API, so a dropped `user.updated`
webhook would leave the column permanently wrong with nothing to correct it. Trading bounded,
self-healing staleness for unbounded staleness *on the authorization path* is a bad trade.

A fork that later needs `WHERE role = 'admin'` should add the column then, and document it as
non-authoritative — mirrored for queryability, never read by `get_current_role`.

### Platform role vs. per-resource capability

Recorded because the next fork will be tempted to break it.

`Role` is the **platform** role: a small, closed, slow-changing set that gates internal
surfaces. Per-resource capability — group moderator, page admin, recruiter — is *not* a role.
It is scoped to a resource, non-exclusive, and revocable, and a single-valued token claim
cannot express any of those three. It belongs in rows, checked per resource.

The failure mode is specific: modelling `recruiter` as a role, hitting the scoping wall, and
"fixing" it by letting users belong to a company with a role — which rebuilds Clerk
Organizations, the thing this fork exists to remove.

---

## Strip order

Load-bearing: **all deletions before the substitution, and the rename last.**

1. **Green baseline.** Full gate set on the unmodified tree. A gate already red proves nothing later.
2. **Supplier domain.** `models/supplier.py`, `services/user/supplier_repository.py`, 3 `UserService`
   methods, `get_supplier_id`/`SupplierID`/`SupplierNotLinkedError`, `handlers/membership.py`,
   supplier branches in `cache.py`, ~11 test files. Most entangled; first, so it stops adding noise.
3. **Second portal.** `apps/supplier-portal`, its services in both compose files, its Traefik
   labels, `SUPPLIER_PORTAL_DOMAIN`, and the `deploy-check` assertions referencing it.
4. **Org → role substitution.** The only real design work. Detailed below.
5. **Roles.** Enum to `user`/`admin`; the 4 guards collapse to `AdminOnly`; `ROLE_LABELS` to English.
6. **Rename** `internal-portal` → `web`. Mechanical but wide: directory, `package.json`, `APP_NAME`
   in both compose files, the Dockerfile, `Makefile:24`'s include path, `deploy-check`, Traefik
   labels. Last, because find-and-replace wants a stable file set.
7. **Squash 3 Alembic migrations into one initial schema.** No production data;
   `docs/setup/making-it-yours.md` §4 endorses this over a rename revision.
8. **Identity + contract.** `[tool.app.metadata]`, `COMPOSE_PROJECT_NAME`, then `make gen-contract`
   **in the same commit** — the one rule in `making-it-yours.md`.
9. **Docs.** Drop `docs/superpowers/`; rewrite `CLAUDE.md`, `docs/setup/making-it-yours.md` and
   `docs/RBAC/roles_definition.md`, all written around suppliers and two portals.
   **Before dropping, extract** — see below.

**Running alongside, from step 1:** a new Clerk instance with Organizations off,
`publicMetadata.role` set on test users, and a session-token customization adding
`"role": "{{user.public_metadata.role}}"`. Step 4 is untestable without it.

---

## The substitution

### Server

`middlewares/auth.py` sets `request.state.role` from a single `role` claim, replacing the
`o.{id,rol}` unpacking and the `removeprefix("org:")`.

`get_current_role` becomes ~10 lines: read `request.state.role`, coerce to `Role`, raise
otherwise. **No Clerk-API fallback** — the token is the only source. This deletes `resolve_org_role`.

That deletion cascades. `services/user/cache.py` holds exactly two caches, `org_role` and
`supplier_id`; both are B2B, so **the whole module goes**, taking `cachetools`, its
per-process-staleness caveat, and the `organizationMembership` dispatcher registrations that
existed to invalidate it.

`resolve_user` loses its `org_id` parameter and both org branches. One is a live landmine:
the JIT path raises `AuthorizationError("Organization membership required")` when a user has
no org — in a consumer app, that is every new signup. **This line must not survive the fork.**

Also removed: `User.org_id` and its line in `anonymize_user`; `update_org_id` in the repository;
`handlers/membership.py`; `get_supplier_id`/`SupplierID`; the four named guards in
`authorization.py`, which collapse to `AdminOnly = require_role(Role.ADMIN)` over the unchanged
`require_role` factory.

**Dead code removed in passing:** `middlewares/auth.py:35` skips Clerk parsing entirely for
`/public/*`, citing `link_token` as the credential. There are no `/public/*` routes and
`link_token` appears nowhere else in the codebase. A path prefix that bypasses auth with nothing
behind it is not inherited silently.

### Frontend

`permissions.ts` keeps its shape — `getUserRole` remains the single seam, it just stops
stripping a prefix. `isInternalRole`/`isSupplierRole` become `isAdmin`; `ROLE_LABELS` to English.

What genuinely changes is *where the role is read*. `proxy.ts` runs at the edge with only the
token, so it reads the custom session claim via `auth()` → `sessionClaims.role`. `provider.tsx`
could read `useUser().publicMetadata.role` directly instead, but uses `sessionClaims` too, so
there is exactly one source and the portability-seam comment stays true. **Confirm the exact
accessor against the installed `@clerk/nextjs` v6 minor before writing it.**

`user-panel.tsx` loses `onOpenOrganizationProfile` and the "Organisation" menu item;
`clerk-user-panel.tsx` loses `openOrganizationProfile`.

### A property that will look like a regression and is not

Today a revoked role is bounded by a 60s cache TTL plus webhook invalidation. With role-on-token
the bound becomes the session token lifetime — short by default in Clerk and refreshed
automatically, so the same order of magnitude. **Confirm the lifetime on the new instance
rather than assuming it.**

---

## Verification gates

The template's existing harness; no new tooling.

| After | Gate |
|---|---|
| Baseline | all of the below, green, on the unmodified tree |
| Supplier strip | `cd server && make test` |
| Portal strip | `make check-web`; `docker compose -f docker-compose.prod.yml config` |
| Role substitution | `cd server && make test`, plus the live request below |
| Rename | `bash scripts/verify-infra.sh`; `make docker-run-core` boots |
| Migration squash | `make docker-migrate` from an empty volume, then `make docker-migrate-status` |
| Identity + contract | `make check-contract` |
| Final | `make check`; `make deploy-check`; `git grep` sweep for `supplier`, `org_id`, `orgRole`, `internal-portal` |

**The live request is the gate that matters most and cannot be automated.** Sign in on the new
Clerk instance; call an `AdminOnly` endpoint as `user` and expect 403, then as `admin` and expect
200. That exercises the claim, the middleware, `get_current_role` and `require_role` end to end.

---

## Known traps carried forward

Inherited, not introduced. Each is documented here so the fork does not rediscover them.

**Both portal images build with one Clerk key.** `Makefile:24` includes only
`web-app/apps/internal-portal/.env.local`, and both portal services in `docker-compose.dev.yml:12,31`
read the same bare `${NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY}`. Harmless at one app. It becomes a live
bug the day a second app needs a different Clerk instance — which is exactly the admin-console
case — and `deploy-check` will not catch it, since it asserts only that each image baked its own
`APP_NAME`. After the rename this reads `web-app/apps/web/.env.local`; the single-include shape
is unchanged.

**`ALLOWED_ORIGINS` gates auth, not just CORS.** `server/app/core/config.py:217` feeds both CORS
and the Clerk `azp` token-party check (`server/app/utils/auth.py:72`). A missing portal origin
presents as broken authentication, not as a config error.
(`CLAUDE.md` cites `:208` for this; it has drifted — the field is at `:217` as of `cfca621`.)

**`deploy-check` does not prove the Traefik labels.** It proves the file parses under `APP_ENV`,
that images build distinctly, that a failed migration fails the stack, and that nothing publishes
a host port. Routing correctness rides on review plus the first real deploy — and the fork
*changes* the labels (supplier-portal removed, internal-portal renamed), so the B2C label set is
not the one a B2B deploy would have proven.

**WS7 is inherited unfixed.** `chatbot.py`'s `event_generator()` never checks for client
disconnect, so a client leaving mid-stream keeps consuming LLM output. Deferred by standing
decision; whichever repo needs the chatbot first fixes it and the other ports it.

**`web-app/packages/types` has no `tsconfig.json`**, so root `pnpm type-check` cannot check all
packages. Pre-existing since the initial commit.

---

## Extract before dropping `docs/superpowers/`

Deployment targets Dokploy, so one section survives the directory's removal — relocated,
not carried. `2026-09-03-ws2-traefik-dokploy-deploy-design.md` is 360 lines, ~320 of which
are B2B history (the compose repair, WS2 decisions, acceptance for shipped work, the
superseded tunnelled-staging appendix). Its **"How Dokploy actually configures Traefik"**
section is not history — it is sourced operational fact:

- entrypoints `web` (80) / `websecure` (443); cert resolver named `letsencrypt`, HTTP
  challenge, applied only to `websecure` routers
- `dokploy-network`: a Compose deployment lands only in its own project network unless the
  file joins `dokploy-network` explicitly. Dokploy issue #3435, still open, and *the single
  most common cause of a deploy that builds cleanly and then 404s*
- Dokploy's Domains tab and hand-written labels are **both** labels — the risk in mixing
  them is two routers matching one Host, not two competing systems (issue #3222)

**Action:** lift it into `docs/setup/deploy-dokploy.md` in the target, next to
`infrastructure.md` and `clerk.md`, correcting the `config.py:208` reference it shares with
`CLAUDE.md` (see Known traps). The current home was always wrong for it — a reader asking
"how do I deploy this" does not look in a dated workstream spec, and `infrastructure.md`
mentions Dokploy and Traefik in three lines total.

Then drop the directory.

---

## Out of scope

- The social-network domain. This template ships none of it.
- An admin console. `apps/` is kept so one is cheap to add; no shell is shipped.
- Any per-resource capability system.
- WS7.
- Fixing the single-Clerk-key build-arg shape. Documented above; not triggered at one app.
