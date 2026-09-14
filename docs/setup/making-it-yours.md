# Making It Yours

How to turn this template into your project: renaming the service, replacing the
branding, and — if the shipped example domain doesn't fit — replacing that too.

Written from the commit series that renamed this repo from its original product name to
Template App, so every step below is one that was actually needed rather than one that
seemed likely.

Companion: [`clerk.md`](./clerk.md) for the dashboard side, which §4 depends on.

---

## The one rule

**`server/pyproject.toml` is the single source of the service's public identity, and
changing it is a contract change.** The title lands verbatim in the committed
`server/openapi.json` and in the header of all 31 generated client files. Change it and
regenerate in the *same commit*, or CI fails on the next push.

---

## 1. Service identity

`server/pyproject.toml`:

```toml
[project]
version = "1.0.0"                      # bumping this is also a contract change
description = "..."                    # packaging metadata only

[tool.app.metadata]
title = "Your App - Server"            # → openapi.json info.title, every client header
description = "..."                    # → openapi.json info.description
api_v1_str = "/api/v1"                 # → prefix on every versioned path
```

Then, from the repo root:

```bash
make gen-contract     # rewrites openapi.json + the 31 generated client files
git add -A            # stage the artifacts WITH the pyproject change
```

> **The pre-commit hook will not save you here.** It regenerates only when a commit
> touches `^server/app/` (`.githooks/pre-commit`), and this change touches
> `server/pyproject.toml`. Run `make gen-contract` yourself. CI
> (`.github/workflows/api-contract.yml`, no path filter) is the backstop, so the failure
> surfaces on push rather than at commit.

Verify with `make check-contract` — it regenerates and fails on any drift.

## 2. Frontend identity

Per portal, in `web-app/apps/<portal>/`:

| What | Where |
|---|---|
| Browser tab title, meta description | `src/app/layout.tsx` → `export const metadata` |
| Sidebar logo alt text | `src/app/(dashboard)/layout.tsx` (internal) / `src/app/(portal)/layout.tsx` (supplier) → `logoAlt` |
| Sidebar mark | `public/images/logo-small.png` |
| Favicon | `public/icons/favicon.ico` |

The two image files are the only branding a text search cannot find. They are per-portal
on purpose — the portals build as distinct images and may carry distinct branding. They
are rendered through `packages/ui/src/components/layout/company-logo.tsx`.

## 3. Docker, Compose and deploy identity

| Setting | Where | What it actually names |
|---|---|---|
| `COMPOSE_PROJECT_NAME` | root `.env` | Compose project, image tags, **and every Traefik router/service label** in `docker-compose.prod.yml` |
| `PROJECT_NAME` | `server/.env.<env>` | the image tag built by `make -C server docker-build`, and nothing else |
| fallback image name | `server/scripts/docker-image-name.sh` | used when `PROJECT_NAME` is unset on a fresh clone |
| `INTERNAL_PORTAL_DOMAIN`, `SUPPLIER_PORTAL_DOMAIN`, `API_DOMAIN` | deploy environment | the hostnames Traefik routes |

> `PROJECT_NAME` is **not** the API's title, despite the name. It tags Docker artifacts.
> The API title is §1. The two are free to differ and setting one does nothing to the
> other.

Verify with `make deploy-check` (and `make deploy-check DEPLOY_ENV=production`). Note
what it does *not* prove — the Traefik labels themselves are never exercised; see the
checklist in `docs/superpowers/specs/2026-09-03-ws2-traefik-dokploy-deploy-design.md`.

## 4. The example domain

The template ships supplier document compliance as a worked example. None of it is
load-bearing — the multi-tenancy, auth, contract and deploy machinery do not depend on
it. Replace it when it doesn't fit:

| Concept | Where it lives |
|---|---|
| `Supplier` model | `server/app/models/supplier.py`, `server/alembic/versions/*_add_supplier_table.py`, `server/app/services/user/supplier_repository.py` |
| Supplier-scoped identity | `get_supplier_id()` / `SupplierID` / `SupplierNotLinkedError` in `server/app/api/dependencies/authentication.py` |
| Role names | `server/app/models/enums.py` **and** `web-app/packages/auth/src/permissions.ts` — **and the Clerk dashboard** (see [`clerk.md`](./clerk.md) §2) |
| The external portal's name | `web-app/apps/supplier-portal/` (directory, `package.json` name, `APP_NAME` in both compose files, `SUPPLIER_PORTAL_DOMAIN`, and its Traefik labels) |
| Italian UI labels | `ROLE_LABELS` in `packages/auth/src/permissions.ts`; `HUB_NAV` in each portal's `src/lib/hub-nav.ts` |

Two notes on sequencing:

- **Renaming a role is a dashboard change too.** Change the enum without changing the
  Clerk slug and every user silently loses access — `getUserRole()` returns `null`.
- **Renaming the `supplier` table** needs a new Alembic revision. On a template with no
  production data, rewriting the initial migration is cleaner; on a deployed fork it is not.

## 5. Verify the whole rename

```bash
make check-contract              # artifacts match the code that produces them
bash scripts/verify-infra.sh     # layout, identifiers, compose validity
make deploy-check                # the deploy file parses and the stack reaches healthy
cd server && make test           # nothing behavioural moved
```

None of those checks knows your old name. To confirm it is gone, search the tracked
files yourself — `git grep`, not `grep -r`, so gitignored local state (`server/.env.*`,
`server/logs/`) does not report a failure that no rename can fix:

```bash
git grep -Ii your-old-name -- ':(exclude)docs/superpowers'
```

`docs/superpowers/` is excluded on purpose: those are dated design records, and
rewriting them to say something they did not say at the time would falsify the history.

---

## Two traps worth knowing before a first deploy

**`ALLOWED_ORIGINS` gates auth, not just CORS.** A missing portal origin looks like broken
authentication, not a config error. [`clerk.md`](./clerk.md) §4.

**Both portal images are built with the internal portal's `NEXT_PUBLIC_*` build args.**
Compose resolves `build.args` from the invoking shell, and the Makefile exports only
`web-app/apps/internal-portal/.env.local`. Fine while both portals share one Clerk
instance and one API origin; silent the day they must differ. `deploy-check` asserts each
image baked its own `APP_NAME`, not which portal's other values it baked.
