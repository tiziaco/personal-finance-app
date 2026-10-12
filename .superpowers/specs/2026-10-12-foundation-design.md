# Foundation — Personal Finance on the template

**Status:** design approved in conversation, 2026-10-12. Sub-project 1 of 4 of the port.

## Context

The personal finance app (`legacy-v0`) predates the fullstack template and lacks what the
template provides: orval-generated API client, module-first server, infra and deploy
tooling, docs layout, project skills. Most of the legacy app's non-domain code is an early
copy of what became the template, so the port moves domain code onto a newer version of the
same skeleton.

The port is four sub-projects, each with its own spec → plan → implementation:

1. **Foundation** (this spec) — turn the template into a single-tenant B2C base named
   Personal Finance, with no domain code.
2. **Backend modules** — transactions, CSV import, analytics, insights and the finance
   agents as `modules/`, contract regenerated per module.
3. **Frontend** — the finance pages in `apps/web` on the generated hooks, `packages/ui` and
   `packages/data-table`.
4. **Cutover** — merge into `main`, retire the legacy app.

Success for the whole port is feature parity with the legacy app, built on the template, and
staying close enough to the template to merge its future changes.

## Decisions

| Decision | Choice | Why |
|---|---|---|
| Audience | A product for many users, each with isolated data | Stated by the owner |
| Tenant | One user; data keyed by `user_id`. No Clerk Organizations | Owner's choice. Shared households, if ever, are a later migration |
| Roles | None. Every signed-in user is equal | YAGNI; add a flag when an operator page exists |
| Legacy data | None to keep | Dev/test only; one fresh initial migration |
| Frontend layout | Keep the pnpm monorepo, delete `supplier-portal`, rename `internal-portal` → `web` | Shared packages stay as the template has them |
| Product name | "Personal Finance"; compose project `personal-finance` | Matches the repo; rebrand is a `gen-contract` away |
| Strategy | Strip the template first, before any domain code | Every finance module is then written once, against `CurrentUser` |
| Another user's resource | 404, not 403 | Does not confirm the id exists |
| Clerk | Reuse the existing "Personal Finance" instance | Legacy already uses it with no orgs and no webhooks |

## 1. Repository setup

In `personal-finance-app`:

1. `git tag legacy-v0` on `main`.
2. `git worktree add ../pf-legacy legacy-v0`.
3. Copy the legacy app's ignored files into `../pf-legacy`: `.env`, `server/.env.*`,
   `.claude/`, and the ignored parts of `.planning/`. The legacy app runs from there when
   needed; it is a reference, not a working copy. Never run it alongside the new stack —
   both publish port 3000.
4. In the main checkout, `git clean -fdX` after the owner reviews its dry run (`-ndX`), so no
   legacy ignored file survives into the new tree or is overwritten by a template-tracked
   path (the template tracks `.claude/skills/`).
5. `git remote add template ../fullstack-multitenant-next-fastapi-tmp`, fetch, and
   `git switch -c port/template template/main`.

The main checkout is the new app from then on, on the template's default ports, with the
template's worktree tooling working as designed. `main` is untouched until cutover.

Specs and plans follow the template's convention: `.superpowers/specs/` and
`.superpowers/plans/`, committed while in flight; the PR that completes Foundation moves
this spec's lasting facts into `docs/` and deletes it.

## 2. Identity and branding

Per `docs/setup/making-it-yours.md` §1–§3, in one commit with the regenerated contract:

- `server/pyproject.toml` `[tool.app.metadata]` title → "Personal Finance - Server",
  description updated; then `make gen-contract`.
- `COMPOSE_PROJECT_NAME=personal-finance`; `PROJECT_NAME` and the fallback in
  `server/scripts/docker-image-name.sh` likewise.
- `INTERNAL_PORTAL_DOMAIN` → `WEB_DOMAIN`; `SUPPLIER_PORTAL_DOMAIN` removed.
- `template-app.code-workspace` → `personal-finance.code-workspace`.
- Logo and favicon from the legacy `web-app/public/{images,icons}` into
  `apps/web/public/`; page title and metadata "Personal Finance".

## 3. Server

### Supplier example removed

Everything `making-it-yours.md` §4 lists: `app/modules/supplier/`, its import-linter
contracts and R6 layer token, its imports in `alembic/env.py` and `app/main.py`, its row in
the tenant-tables test, its unit and integration tests, and the supplier assertions in
`test_auth_delete.py`. The `/public/*` carve-out in `AuthMiddleware` existed only for the
supplier link-token flow and goes too.

### Organisations and roles removed

- `AuthMiddleware` sets `request.state.clerk_id` from `sub` and nothing else; it stays
  permissive.
- `account` keeps: `CurrentUser` / `get_current_user`, JIT provisioning as
  `resolve_user(session, clerk_id)`, erasure, the `user.created|updated|deleted` webhook
  handlers, `UserResponse`, `UserAlreadyExistsError`, `USER_ERASING`, `USER_SYNCED`.
- `account` loses: `Role`; `CurrentRole`, `get_current_role`, `require_role` and the guards
  `InternalUserRole`, `PMOnly`, `ReviewerRole`, `SupplierRole`; `CurrentOrgId`,
  `get_current_org_id`; `resolve_org_role`; JIT's Clerk org-membership lookup and its
  "Organization membership required" error; `cache.py` (it cached only org roles) and every
  `user_cache` call; the membership webhook handlers; `USER_OFFBOARDED`;
  `user_repository.update_org_id` and the `org_id` parameter of `create` / `create_or_get`.
- `merge_clerk_metadata` reduces to the user's `public_metadata`.
- `integrations/clerk/client.py` loses `get_first_org_membership`.
- `User` loses `org_id`, and `anonymize_user()` the line clearing it.

`USER_SYNCED` has no subscriber after this; it stays as the hook for first-sign-up seeding
(default categories, say) in the backend sub-project.

### Ownership replaces tenancy

- `TenantMixin` in `app/models/base.py` becomes `UserOwnedMixin`:
  `user_id: uuid.UUID`, foreign key to `user.id`, indexed, not nullable.
- `Conversation` adopts it (it already has that column).
- `tests/unit/models/test_tenant_tables.py` becomes `test_owned_tables.py`: every table
  carries `UserOwnedMixin` or is allowlisted with a reason. The allowlist is `user` alone.
- The scoping rule is a convention, as in the template today: every repository query on an
  owned table filters by the caller's `user_id`; a single-row lookup goes through an
  ownership dependency in the owning module (the `UserConversation` pattern).
- A missing row and another user's row both return **404**. The template's ownership
  dependencies that return 403 for another user's row change to 404.

### Errors after the change

No token → 401. A signed-in user is never refused for lacking an organisation or a role;
no server route returns a role-based 403.

### Migrations

The template's three revisions are replaced by one initial migration: `user` (no
`org_id`) and the conversation tables. Each backend module adds its own revision later.

### Tests

- Delete supplier, role and org-membership tests; rewrite account tests that pass `org_id`.
- Add a regression test: a valid token with no `o` claim reaches a `CurrentUser` route
  and gets 200.
- Add a test that another user's conversation returns 404.
- `test_module_contracts.py` and `test_main_imports_every_module_explicitly` stay.

## 4. Web app and infra

### One app

- Delete `web-app/apps/supplier-portal/`; `git mv apps/internal-portal apps/web`;
  `package.json` name `web`.
- Update every reference: `web-app/Dockerfile` (per-app `COPY`s; `APP_NAME=web`),
  `web-app/package.json` scripts (`dev`; no `dev:supplier`), both compose files (one `web`
  service), prod Traefik labels (`${COMPOSE_PROJECT_NAME}-web` on `WEB_DOMAIN`), root
  `Makefile`, VS Code `Dev: *` tasks, the worktree port-slot scripts (no supplier port),
  `scripts/verify-infra.sh`, `make deploy-check`.

### Auth

- Delete `packages/auth/src/permissions.ts` and its test (`Role`, `getUserRole`,
  `isInternalRole`, `isSupplierRole`, `ROLE_LABELS`).
- `AuthProvider` / `useAppAuth` stay, without `role`; `AppUser` is identity only. The
  package remains the one place the app touches Clerk's hooks.
- `apps/web/src/proxy.ts`: public routes `/sign-in(.*)` and `/sign-up(.*)`; everything
  else `auth.protect()`. The role guard, `/unauthorized` and its page are deleted. The
  `/` → `/home` redirect and its comment stay.
- Sign-up page from legacy: `(auth)/sign-up/[[...sign-up]]/page.tsx`.
- `clerk-user-panel.tsx` drops `onOpenOrganizationProfile`;
  `packages/components/src/layout/user-panel.tsx` drops the prop and its "Organisation"
  item; tests follow.

### Pages

Delete the example `orders/` and `projects/` pages. Foundation leaves `home` (a
placeholder) and the existing settings (general, server status). `HUB_NAV` is Home only;
finance pages arrive in sub-project 3.

### Generated client

Regenerated by `make gen-contract` after the server changes; never edited by hand.

## 5. Clerk

Reuse the existing "Personal Finance" development instance.

- `CLERK_APP_ID` in the root `.env`, so `make clerk-setup` skips app creation. Keys go into
  the per-service env files from the legacy `.env`.
- Run `make clerk-pull-config` first and diff it against `scripts/clerk/config.json`.
  Settings the instance already has (social providers, password rules, name fields) are
  adopted into `config.json`, so `apply-config` does not overwrite them.
- `config.json`: `sign_up_mode` `public`; `organization_settings` reduced to
  `enabled: false`; `x_organization_roles` removed.
- Delete `apply-roles.sh` and `make clerk-apply-roles`; `clerk-setup` runs
  bootstrap-env (skipped) → apply-config → seed-users. `apply-config.sh` no longer strips
  `x_organization_roles`. `pull-config.sh` and `check-config.sh` stay.
- `seed-users.sh` and `server/data/clerk-dev-seed.json`: no organisation, no roles; two
  users, `dev-alice@example.com` and `dev-bob@example.com`, for manual isolation checks.
- OAuth (Swagger): reuse the legacy app's OAuth client; add the new server's callback URL
  (port 8100) to its redirect URIs, keeping the legacy one until cutover. Do not run
  `bootstrap-oauth.sh`.
- Webhook: add one endpoint for the new app, subscribed to `user.created`,
  `user.updated`, `user.deleted`. The legacy app has none.
- Existing instance users are JIT-provisioned into the new database on first sign-in.

## 6. Docs and skills

**Delete:** `docs/data-model/supplier.md`, `docs/product/features/suppliers.md`,
`docs/setup/making-it-yours.md`.

**Rewrite:** `architecture/authorization.md` (user as tenant, `UserOwnedMixin`, the
owned-tables test, ownership dependencies, 404, no roles); `setup/clerk.md` (§5 of this
spec, including reuse of an existing instance); `product/prd-mvp.md` and
`product/README.md`; `product/features/account.md` and `data-model/account.md`.

**Edit:** `architecture/authentication.md`, `architecture/server.md`,
`architecture/web-app.md`, `setup/deploy-dokploy.md`, `setup/infrastructure.md`, root
`README.md`, and the root, `server/` and `web-app/` `CLAUDE.md` (the root opening
describes the B2C finance app).

**Add:** `docs/product/features/{transactions,csv-import,categorisation,analytics,insights,chat,budgets}.md`,
written from the legacy `.planning/` (`PROJECT.md`, `research/FEATURES.md`, `ROADMAP.md`)
and the legacy code. `budgets.md` records the feature as not built (legacy has a
"Coming soon" page and no backend); it is out of scope for the port. Data-model docs for
finance tables are written per module in sub-project 2.

`.planning/` is not carried over; it stays in `legacy-v0`.

**Tracking:** `ROADMAP.md` lists the four sub-projects, Foundation in progress.
`TODO.md` and `BUGS.md` keep only entries that still apply.

**Skills:** remove `.claude/skills/clerk-orgs` and its `skills-lock.json` entry. Remove
organisation and role content from `server-patterns`, `server-testing`,
`web-app-patterns`, `web-app-testing`, `run-stack`, `worktrees`, `deploy-check`. Other
vendored `clerk-*` skills stay as they are. Diff the legacy FastAPI service skill against
`server-patterns` and merge what it has that the template lacks.

## 7. Commit sequence

Each commit leaves every check green.

1. This spec.
2. Remove the supplier example (server, web, tests, docs).
3. Remove organisations and roles from the server; `UserOwnedMixin`; regression tests;
   replace the migrations with one initial migration (the `User` model changes here, so
   the migrations must change with it).
4. Remove organisations and roles from the web app; Clerk config and scripts.
5. Identity rename, `internal-portal` → `web`, compose, Traefik, worktree scripts,
   branding.
6. Docs and skills, including the product docs from `.planning/`.

## 8. Definition of done

- `make test`, `make check-server` (lint-imports included), `make check-contract`, web
  tests, lint, type-check and production build, `bash scripts/verify-infra.sh`,
  `make deploy-check` all pass.
- `make docker-run` brings up `web`, `server`, `migrate` and Postgres; a new user signs up
  in the browser and lands on `/home`; the server status check reads healthy.
- Alice and Bob each sign in; `GET /api/v1/auth/me` returns each one's own row.
- `git grep -Ii -E "supplier|organi[sz]ation|org_id|project_manager"` returns only
  intentional hits (the vendored `clerk-*` skills).
- The spec's lasting facts are in `docs/` and this file is deleted, in the PR that
  completes Foundation.

## Out of scope

Any finance module or page (sub-projects 2 and 3); budgets; households and sharing; roles
or an admin flag; paid tiers; the merge into `main` (sub-project 4).
