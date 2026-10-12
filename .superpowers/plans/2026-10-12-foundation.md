# Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the multi-tenant B2B template on `port/template` into a single-tenant B2C base named Personal Finance — no supplier example, no Clerk Organizations, no roles, one `web` app, public sign-up — with every check green and no finance code yet.

**Architecture:** Subtractive. The supplier module and portal go first, then the server's ownership model changes (user is the tenant, `UserOwnedMixin`, 404 for another user's row), then orgs and roles leave the server, the web app and the Clerk tooling, then the identity rename, then docs and skills. Every task ends with a commit that leaves the whole suite green.

**Tech Stack:** FastAPI + SQLModel + Alembic + pytest (testcontainers Postgres 18), import-linter; pnpm Next.js 16 monorepo + Vitest; orval contract codegen; Clerk (CLI + Backend API); Docker Compose, Traefik.

**Spec:** `.superpowers/specs/2026-10-12-foundation-design.md`

## Global Constraints

- Work on branch `port/template` in `/Users/tizianoiacovelli/projects/personal-finance-app`. Never commit to `main`. Never `git push` without being asked; when asked, `git push -u origin port/template`.
- Product name "Personal Finance"; API title "Personal Finance - Server"; compose project `personal-finance`.
- The user is the tenant. No Clerk Organizations, no roles, no admin flag.
- A missing row and another user's row both answer **404** with the same error code.
- One web app at `web-app/apps/web` (package `@app/web`; `pnpm --filter web` selects it, as `internal-portal` does today).
- Never hand-edit `server/openapi.json` or `web-app/packages/api-client/src/generated/**` — run `make gen-contract` from the repo root and commit what it produces in the same commit as the server change.
- Never hand-edit `web-app/pnpm-lock.yaml` — run `pnpm install` in `web-app/`.
- No production data exists: migrations may be rewritten in place.
- The legacy app is a read-only reference at `/Users/tizianoiacovelli/projects/pf-legacy`. Never run it at the same time as this stack (both publish port 3000).
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Steps marked **[USER]** need the human (dashboard clicks, Clerk CLI login, a browser). Steps marked **[CONFIRM]** change the live Clerk instance; ask before running them.

## Review Focus

1. **A new user signs up and immediately uses the app.** No org, no role, no invitation — the first authenticated request JIT-provisions the row and returns 200. Pinned by the HTTP-level test in Task 4 and the browser check in Task 11.
2. **Another user's conversation is indistinguishable from a missing one** — same 404, same `CONVERSATION_NOT_FOUND`, and the message names no user id. Pinned in Task 3.
3. **An org claim on a token is ignored, not honoured.** A token that still carries `o` (from a stale session or a Clerk default) must not put `org_id`/`org_role` on `request.state`. Pinned in Task 4.
4. **A signed-out visitor can reach `/sign-up`** and is not bounced to `/sign-in`, and a signed-in user is never sent to an `/unauthorized` page that no longer exists. Pinned by the browser check in Task 11.
5. **A new owned table cannot slip in unscoped.** `test_owned_tables.py` fails for any table without `UserOwnedMixin` unless allowlisted with a reason, and CI runs it. Pinned in Task 3.

---

## File map

**Deleted:** `server/app/modules/supplier/**`, `server/tests/{unit,integration}/modules/supplier/**`, `server/alembic/versions/20260825_0838_9bcca25cfef3_add_supplier_table.py`, `server/alembic/versions/20260825_0900_b3f1c27a4e18_make_user_org_id_nullable.py`, `server/app/modules/account/cache.py`, `server/tests/unit/modules/account/{test_cache,test_dependencies}.py`, `server/tests/integration/modules/account/test_dependencies.py`, `server/tests/unit/models/test_tenant_tables.py` (replaced), `web-app/apps/supplier-portal/**`, `web-app/packages/auth/src/permissions{,.test}.ts`, `web-app/apps/internal-portal/src/app/unauthorized/`, `web-app/apps/internal-portal/src/app/(dashboard)/{orders,projects}/`, `scripts/clerk/apply-roles.sh`, `docs/data-model/supplier.md`, `docs/product/features/suppliers.md`, `docs/setup/making-it-yours.md`, `.claude/skills/clerk-orgs/`, `template-app.code-workspace` (renamed).

**Created:** `server/tests/unit/models/test_owned_tables.py`, `web-app/apps/web/src/app/(auth)/sign-up/[[...sign-up]]/page.tsx`, `docs/product/features/{transactions,csv-import,categorisation,analytics,insights,chat,budgets}.md`, `personal-finance.code-workspace`.

**Moved:** `web-app/apps/internal-portal/` → `web-app/apps/web/`.

**Modified (main ones):** `server/app/models/base.py`, `server/app/api/middlewares/auth.py`, `server/app/modules/account/{__init__,dependencies,models,repository,service,webhooks}.py`, `server/app/modules/account/router/auth.py`, `server/app/modules/conversation/{__init__,dependencies,exceptions,models}.py`, `server/app/integrations/clerk/{client,timestamps}.py`, `server/app/core/events.py`, `server/app/main.py`, `server/alembic/env.py`, `server/alembic/versions/20260411_1650_0c7838405158_initial_schema.py`, `server/pyproject.toml`, `web-app/packages/auth/src/{index.ts,provider.tsx,provider.test.tsx}`, `web-app/packages/components/src/layout/user-panel{,.test}.tsx`, the app's `proxy.ts`, `clerk-user-panel{,.test}.tsx`, `hub-nav.ts`, `layout.tsx` files, `scripts/clerk/*`, `scripts/worktree/{init,clean}.sh`, `scripts/deploy-check.sh`, `Makefile`, `server/Makefile`, `server/scripts/{compose-env,docker-image-name}.sh`, both compose files, `web-app/{Dockerfile,package.json,vitest.config.mts}`, `.vscode/{settings,tasks}.json`, `.github/workflows/module-boundaries.yml`, `.env.example`, `server/.env.example`, every doc and project skill listed in Tasks 8–10.

---

### Task 0: Workspace preflight (no commit)

Gets a green baseline before anything changes, so a later red is attributable.

**Files:** only gitignored env files and dependency directories.

- [ ] **Step 1: Docker and hooks**

Start Docker Desktop, then:

```bash
cd /Users/tizianoiacovelli/projects/personal-finance-app
docker info --format '{{.ServerVersion}}'      # must print a version
git config core.hooksPath .githooks
git status --short                            # must be empty
```

- [ ] **Step 2: Env files from the examples, values from legacy**

```bash
cp .env.example .env
cp server/.env.example server/.env.development
cp server/.env.example server/.env.test
cp web-app/apps/internal-portal/.env.example web-app/apps/internal-portal/.env.local
cp web-app/apps/supplier-portal/.env.example web-app/apps/supplier-portal/.env.local   # deleted in Task 2; needed until then
```

Fill them from the legacy files (read `../pf-legacy/.env`, `../pf-legacy/server/.env.development`, `../pf-legacy/web-app/.env.local`; never print secret values into logs or commits):

| Target | Key | Source |
|---|---|---|
| `.env` | `COMPOSE_PROJECT_NAME` | `personal-finance` |
| `.env` | `GRAFANA_ADMIN_PASSWORD`, `NGROK_DOMAIN`, `NGROK_AUTHTOKEN` | legacy `.env` if present, else leave `change-me` |
| `.env` | `CLERK_APP_ID` | **[USER]** run `clerk apps list` (after `clerk auth login` if needed) and pick the "Personal Finance" app id |
| `server/.env.development` and `server/.env.test` | `CLERK_SECRET_KEY`, `CLERK_ISSUER`, `CLERK_OAUTH_CLIENT_ID`, `CLERK_AUTHORIZE_URL`, `CLERK_TOKEN_URL`, `OPENAI_API_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` | legacy `server/.env.development` (same names) |
| `server/.env.test` | `APP_ENV` | `test` |
| both portal `.env.local` | `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY` | legacy `web-app/.env.local` |

`CLERK_WEBHOOK_SIGNING_SECRET` stays `change-me` until Task 6.

- [ ] **Step 3: Install dependencies**

```bash
cd server && uv sync && cd ..
cd web-app && pnpm install && cd ..
```

- [ ] **Step 4: Baseline**

```bash
make -C server test          # unit + integration; needs Docker
make check                   # ruff, format, lint-imports, eslint, prettier
make test-web
make check-contract
```

Expected: all pass. If anything fails, **stop** and report the failure verbatim — do not start Task 1 on a red baseline.

---

### Task 1: Remove the supplier module from the server

**Files:**
- Delete: `server/app/modules/supplier/` (8 files), `server/tests/unit/modules/supplier/` (4 files), `server/tests/integration/modules/supplier/` (2 files), `server/alembic/versions/20260825_0838_9bcca25cfef3_add_supplier_table.py`
- Modify: `server/app/main.py:40-46`, `server/pyproject.toml` (`[tool.importlinter]`), `server/alembic/env.py:31`, `server/alembic/versions/20260825_0900_b3f1c27a4e18_make_user_org_id_nullable.py:13,27`, `server/app/core/events.py:3-4`, `server/app/api/middlewares/auth.py:34-38`, `server/app/modules/account/{dependencies.py:3, router/auth.py:58-69, service.py:197-199, webhooks.py:421-434}`
- Modify tests: `server/tests/unit/models/test_tenant_tables.py:22`, `server/tests/unit/models/test_uuid_primary_key.py`, `server/tests/{unit,integration}/conftest.py`, `server/tests/integration/modules/account/test_service.py`, `server/tests/integration/modules/account/router/{test_auth_delete,test_webhooks}.py`, `server/tests/README.md:72,78`
- Delete docs: `docs/data-model/supplier.md`, `docs/product/features/suppliers.md`; modify `docs/README.md:30,42`

**Interfaces:**
- Produces: `app.modules` contains exactly `account` and `conversation`. `USER_SYNCED` and `USER_OFFBOARDED` have no subscribers; `USER_ERASING` has one (`conversation`).

- [ ] **Step 1: Delete the module, its tests and its migration**

```bash
cd /Users/tizianoiacovelli/projects/personal-finance-app
git rm -r -q server/app/modules/supplier server/tests/unit/modules/supplier server/tests/integration/modules/supplier
git rm -q server/alembic/versions/20260825_0838_9bcca25cfef3_add_supplier_table.py
git rm -q docs/data-model/supplier.md docs/product/features/suppliers.md
```

- [ ] **Step 2: Run the contract tests to see them fail**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/test_module_contracts.py -v`
Expected: FAIL — `test_main_imports_every_module_explicitly` and the env.py check name a module that no longer exists (or collection fails on `from app.modules import supplier`).

- [ ] **Step 3: Wiring — main.py, env.py, import-linter, migration chain**

`server/app/main.py` lines 40-46 become:

```python
# Every module by name, whether or not it has a router. A module that only
# subscribes to events would otherwise never be imported, and
# events.publish() would run zero handlers with no error.
# tests/unit/test_module_contracts.py checks this list against app/modules/.
from app.modules import account as _account
from app.modules import conversation as _conversation
```

`server/alembic/env.py`: delete the line `import app.modules.supplier.models`.

`server/pyproject.toml`, in `[tool.importlinter]`:
- R6 layers: `"app.modules.conversation | app.modules.supplier",` → `"app.modules.conversation",` and delete the comment line above it (`# '|' forbids these siblings ...`).
- `R1: account`: `forbidden_modules = ["app.modules.conversation.*"]`
- `R1: conversation`: `forbidden_modules = ["app.modules.account.*"]`
- Delete the whole `R1: supplier` contract block (last block in the file).

`server/alembic/versions/20260825_0900_b3f1c27a4e18_make_user_org_id_nullable.py`: docstring `Revises: 9bcca25cfef3` → `Revises: 0c7838405158`; `down_revision = "9bcca25cfef3"` → `down_revision = "0c7838405158"`. (This file is deleted in Task 4; this keeps the chain valid until then.)

- [ ] **Step 4: Code that names supplier**

- `server/app/core/events.py:3-4`: "`conversation` and `supplier` import `account`, so `account` cannot import them." → "`conversation` imports `account`, so `account` cannot import it."
- `server/app/api/middlewares/auth.py:34-38`: delete the `/public/*` carve-out block (the comment and the `if request.url.path.startswith("/public/"): return await call_next(request)`). Nothing routes under `/public/`.
- `server/app/modules/account/dependencies.py:3`: `("does this supplier own this order?")` → `("does this user own this conversation?")`.
- `server/app/modules/account/router/auth.py` `delete_me` docstring steps become:

```
    1. Delete user from Clerk (invalidates all future JWTs)
    2. Soft-delete all conversation records + collect their IDs
    3. Clear LangGraph checkpoint data for each conversation (message PII)
    4. Delete mem0 long-term memory (extracted fact PII)
    5. Anonymize the user record in DB
    6. Invalidate the org-role cache
```

- `server/app/modules/account/service.py:197-199` comment → `# anonymised — conversation soft-delete, checkpoints and names. Their` / `# identifiers are what anonymize_user() destroys.`
- `server/app/modules/account/webhooks.py` `handle_membership_deleted` docstring: delete the sentences about unlinking a supplier and `Supplier.contact_id`, and the last line `Publishes USER_OFFBOARDED; the supplier module unlinks the contact.` → `Publishes USER_OFFBOARDED.` (The handler itself goes in Task 4.)

- [ ] **Step 5: Tests that name supplier**

- `server/tests/unit/models/test_tenant_tables.py`: delete the `"supplier": ...` ALLOWLIST row.
- `server/tests/unit/models/test_uuid_primary_key.py`: delete `from app.modules.supplier.models import Supplier`; `TABLES = [User, Conversation]`; delete the `Supplier: lambda: ...` factory entry; the parametrised FK column list becomes `[Conversation.__table__.c.user_id]`.
- `server/tests/unit/conftest.py` and `server/tests/integration/conftest.py` `clear_user_cache`: delete `from app.modules.supplier.cache import supplier_cache` and both `supplier_cache.reset()` lines.
- `server/tests/integration/modules/account/test_service.py`: delete the three supplier imports and `class TestSupplierRelinkInvalidation` (to end of file); delete now-unused imports (`pytest_asyncio`, `MISS`, `user_cache` if unused — let ruff tell you).
- `server/tests/integration/modules/account/router/test_auth_delete.py`: delete the `supplier_cache` / `Supplier` imports; in `TestDeleteMeCacheInvalidation` make the docstring `"""Account deletion must not leave the cached org role behind."""`, rename `test_clears_both_caches` → `test_clears_the_role_cache` and delete its two supplier lines, change its cached role `"supplier"` → `"reviewer"`, delete `test_supplier_is_unlinked`, reword `test_org_id_is_cleared`'s docstring to `"""org_id is dropped with the rest of the user's personal data."""`, and delete the two `supplier_cache` lines in `test_unrelated_users_are_untouched`.
- `server/tests/integration/modules/account/router/test_webhooks.py`: delete `from app.modules.supplier.models import Supplier`, delete `test_membership_deleted_for_matching_org_unlinks_supplier`, and in `test_membership_deleted_for_different_org_leaves_state_intact` delete the Supplier construction and its assertion, keeping the `org_id == "org_e2e"` check.
- `server/tests/README.md:72,78`: "Resets the user and supplier caches" → "Resets the user cache".
- `docs/README.md`: delete the `features/suppliers.md` and `data-model/supplier.md` index rows.

- [ ] **Step 6: Verify**

```bash
cd server
uv run ruff check . && uv run ruff format --check . && uv run lint-imports
make test
cd .. && make check-contract
git grep -n -i "supplier" -- server/app server/tests server/alembic server/pyproject.toml
```

Expected: all green; `check-contract` clean (supplier had no routes); the grep returns only `server/app/modules/account/models.py` (`Role.SUPPLIER`, the `org_id` docstring), `server/app/modules/account/{__init__,dependencies}.py` (`SupplierRole`), and role-string uses in account tests — all removed in Task 4.

- [ ] **Step 7: Commit**

```bash
git add -A server docs
git commit -m "refactor(server): remove the supplier example module

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Remove the supplier portal and its infra

**Files:**
- Delete: `web-app/apps/supplier-portal/` (30 files)
- Modify: `web-app/{package.json:7, vitest.config.mts:37,45, Dockerfile:23,40,45}`, `docker-compose.dev.yml:23-39`, `docker-compose.prod.yml:55-85`, `.env.example:13`, `server/.env.example:7`, `Makefile` (lines listed below), `scripts/worktree/init.sh`, `scripts/worktree/clean.sh`, `scripts/deploy-check.sh`, `scripts/clerk/bootstrap-env.sh:21,99-100`, `.vscode/settings.json:16`, `.vscode/tasks.json`, `web-app/apps/internal-portal/src/app/layout.tsx:15`, `web-app/pnpm-lock.yaml` (regenerated)

**Interfaces:**
- Produces: one web app, still at `apps/internal-portal` (renamed in Task 7). No `SUPPLIER_PORTAL_*` variable, no port 3002, no `dev-supplier`.

- [ ] **Step 1: Delete the app and regenerate the lockfile**

```bash
git rm -r -q web-app/apps/supplier-portal
rm -rf web-app/apps/supplier-portal          # its untracked .env.local from Task 0
cd web-app && pnpm install && cd ..
```

- [ ] **Step 2: web-app wiring**

- `web-app/package.json`: delete `"dev:supplier": "pnpm --filter supplier-portal dev",`.
- `web-app/vitest.config.mts`: delete `portal("supplier-portal"),`; comment line 37 → `// Each app owns \`@/\`, so the alias is per project.`
- `web-app/Dockerfile`: delete `COPY apps/supplier-portal/package.json ./apps/supplier-portal/` and `COPY --from=deps /app/apps/supplier-portal/node_modules ./apps/supplier-portal/node_modules`; comment line 45 → `# Copy the apps (the pnpm workspace filter resolves against them)`.
- `web-app/apps/internal-portal/src/app/layout.tsx:15` description → `"Personal Finance — track your spending, understand where it goes, and save more."` (title changes in Task 7).

- [ ] **Step 3: Compose and env examples**

- `docker-compose.dev.yml`: delete the whole `supplier-portal:` service (lines 23-38) and the whitespace-only line after it.
- `docker-compose.prod.yml`: delete the whole `supplier-portal:` service (lines 55-85, including its Traefik labels and the 3000/3002 comment).
- `.env.example`: delete `SUPPLIER_PORTAL_HOST_PORT=3002`.
- `server/.env.example:7`: `ALLOWED_ORIGINS='["http://localhost:3000", "http://localhost:8100"]'`. Apply the same edit to your local `server/.env.development` and `server/.env.test`.

- [ ] **Step 4: Makefile**

- `.PHONY` (line 1): drop `dev-supplier`.
- Lines 11-14 become:

```make
# Host port for the web app, on both paths: compose publishes it, and
# dev-internal hands it to `next dev` as PORT.
INTERNAL_PORTAL_HOST_PORT ?= 3000
```

- Help: line 45 `Check ports $(API_HOST_PORT)/$(INTERNAL_PORTAL_HOST_PORT) are free`; delete line 47 (`dev-supplier`); line 48 `Kill whatever listens on $(API_HOST_PORT), $(INTERNAL_PORTAL_HOST_PORT) and 4040`; line 80 `Build the web app only`.
- `dev-preflight` (lines 109, 113, 118): remove `$(SUPPLIER_PORTAL_HOST_PORT)` from the loop, the message (`The Docker stack publishes $(INTERNAL_PORTAL_HOST_PORT) and $(API_HOST_PORT)`) and the success echo.
- Delete lines 125-130 (the `INTERNAL_PORTAL_ENV_KEYS` comment and variable, and the `dev-supplier:` target).
- `dev-kill` (line 134): drop `$(SUPPLIER_PORTAL_HOST_PORT)`.
- Lines 268, 273: drop `supplier-portal` from the build lists.
- Lines 293, 311: drop `supplier-portal, ` from the service lists; line 312 drop `supplier-portal` from `up -d`.
- Delete lines 298 and 316 (`Supplier Portal:` URLs).
- Line 367: drop `supplier-portal` from `logs -f`.

- [ ] **Step 5: Scripts**

`scripts/worktree/init.sh`:
- line 6 comment: `else 3000/8100/5434`.
- line 47: `REQUIRED_ENV_FILES=".env server/.env.development web-app/apps/internal-portal/.env.local"`
- lines 67-75 become:

```bash
BASE_INTERNAL="$(base_port INTERNAL_PORTAL_HOST_PORT 3000)"
BASE_API="$(base_port API_HOST_PORT 8100)"
BASE_DB="$(base_port POSTGRES_PORT 5434 server/.env.development)"

slot_ports() { # slot_ports <n> -> "internal api db"
  echo $((BASE_INTERNAL + STEP * $1)) $((BASE_API + STEP * $1)) $((BASE_DB + STEP * $1))
}
```

- line 114: `read -r INTERNAL_PORT API_PORT DB_PORT <<< "$(slot_ports "$SLOT")"`
- delete line 169 (`upsert .env SUPPLIER_PORTAL_HOST_PORT ...`).
- lines 172-173: `"'[\"http://localhost:$INTERNAL_PORT\", \"http://localhost:$API_PORT\"]'"`
- line 174: `for f in web-app/apps/internal-portal/.env.local; do`
- delete line 191 (`Supplier portal:`); line 197 drop `   |   make dev-supplier`.

`scripts/worktree/clean.sh`: line 54 `PORTS="${API_HOST_PORT:?} ${INTERNAL_PORTAL_HOST_PORT:?} 4040"`; line 95 comment `Only the two this project built.`; line 96 `for image in "$PROJECT-server" "$PROJECT-internal-portal"; do`.

`scripts/deploy-check.sh`:
- header (lines 4-11): replace "the two-portal split" / "both portals build as genuinely distinct images" with "the web app and the server build".
- line 47: `for app in internal-portal; do`
- delete line 70 (`SUPPLIER_PORTAL_DOMAIN`).
- lines 83-84: `echo "==> 2/5 Building the web app and the server"` / `"${COMPOSE[@]}" build internal-portal server`
- lines 86-91: header `echo "==> 3/5 Checking the web image baked its APP_NAME"`; comment: `# Without it \`pnpm --filter $APP_NAME build\` has an empty filter.`; loop `for app in internal-portal; do`.
- lines 183-184: `echo "PASS: $COMPOSE_FILE parses, builds the web and server images, gates the"`.

`scripts/clerk/bootstrap-env.sh`: line 21 `PORTALS="web-app/apps/internal-portal"`; lines 99-100 `... are in .env, server/.env.development` / `      and the web app's .env.local."`

- [ ] **Step 6: VS Code**

- `.vscode/settings.json`: delete `"web-app/apps/supplier-portal",` from `eslint.workingDirectories`.
- `.vscode/tasks.json`: delete the `"Dev: Supplier Portal"` task object; remove `"Dev: Supplier Portal"` from both `dependsOn` arrays; details: line 7 `(3000 and 8100 in the main checkout)`, line 18 `(8100/3000 in main)`, line 85 `"API server + web app, no tunnel (2 terminals)"`, line 92 `"API server + web app + ngrok tunnel (3 terminals)"`, line 104 `"... then API server + web app"`, lines 136/145 `(web, server, db, ...)`, line 201 `(web + server)`, line 210 `"Build the web app image"`, line 266 `"Follow logs for web, server, and db"`.

- [ ] **Step 7: Verify**

```bash
make test-web
make check-web
cd web-app && pnpm --filter internal-portal build && cd ..
bash scripts/verify-infra.sh
docker compose -f docker-compose.dev.yml config -q && APP_ENV=staging docker compose -f docker-compose.prod.yml config -q
git grep -n -i -E "supplier-portal|SUPPLIER_PORTAL|dev-supplier|dev:supplier|3002" -- . ':!docs' ':!.claude' ':!.superpowers' ':!**/README.md' ':!CLAUDE.md' ':!**/CLAUDE.md'
```

Expected: tests, lint and build pass; compose files parse (prod may need `INTERNAL_PORTAL_DOMAIN=x NEXT_PUBLIC_API_URL=x` exported for `config`); the grep returns nothing.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "refactor: remove the supplier portal and its infra

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Ownership — UserOwnedMixin, the owned-tables test, 404 for another user's conversation

**Files:**
- Modify: `server/app/models/base.py:95-105`, `server/app/modules/conversation/{models.py:14,40, dependencies.py, exceptions.py, __init__.py}`, `.github/workflows/module-boundaries.yml:47`
- Create: `server/tests/unit/models/test_owned_tables.py`
- Delete: `server/tests/unit/models/test_tenant_tables.py`
- Modify tests: `server/tests/unit/models/test_models.py:10,86-99`, `server/tests/integration/modules/conversation/{test_dependencies.py, router/test_chatbot.py, router/test_conversation.py}`, `server/tests/integration/exceptions/test_handlers.py:33-50`

**Interfaces:**
- Produces: `app.models.base.UserOwnedMixin` with field `user_id: uuid.UUID` (FK `user.id`, indexed, not nullable). `app.modules.conversation` no longer exports `ConversationAccessDeniedError`. `get_user_conversation` raises `ConversationNotFoundError` for a missing, soft-deleted, or another user's conversation.

- [ ] **Step 1: Write the failing tests**

`server/tests/unit/models/test_models.py`: change the import to `from app.models.base import UserOwnedMixin` and replace `class TestTenantMixin` with:

```python
# ============================================================================
# UserOwnedMixin
# ============================================================================


class TestUserOwnedMixin:
    """The column every user-owned table gets (architecture §9)."""

    def test_user_id_is_an_indexed_not_nullable_foreign_key_to_user(self):
        field = UserOwnedMixin.model_fields["user_id"]
        assert field.index is True
        assert field.nullable is False
        assert field.foreign_key == "user.id"

    def test_user_id_is_required(self):
        assert UserOwnedMixin.model_fields["user_id"].is_required()
```

Create `server/tests/unit/models/test_owned_tables.py`:

```python
"""Every table is user-owned or listed here with a reason (architecture §9).

A new table fails this test until it either carries UserOwnedMixin or gets a
row in ALLOWLIST. That is the entire mechanism: the decision cannot be
skipped, only made.
"""

import importlib
import pkgutil

import pytest
from sqlmodel import SQLModel

import app.modules
from app.models.base import UserOwnedMixin

pytestmark = pytest.mark.unit

# Table name -> why it carries no user_id. Delete a row when the table adopts the mixin.
ALLOWLIST: dict[str, str] = {
    "user": "the owner itself: every owned table's user_id points at it",
}


def _import_every_models_slot() -> None:
    for module in pkgutil.iter_modules(app.modules.__path__):
        try:
            importlib.import_module(f"app.modules.{module.name}.models")
        except ModuleNotFoundError as e:
            if e.name != f"app.modules.{module.name}.models":
                raise


def _subclasses(cls: type) -> set[type]:
    found: set[type] = set()
    for sub in cls.__subclasses__():
        found.add(sub)
        found |= _subclasses(sub)
    return found


def _owned_tables() -> set[str]:
    return {
        getattr(cls, "__tablename__", None)
        for cls in _subclasses(SQLModel)
        if issubclass(cls, UserOwnedMixin)
        and cls is not UserOwnedMixin
        and getattr(cls, "__tablename__", None) in SQLModel.metadata.tables
    }


def test_every_table_is_user_owned_or_allowlisted():
    _import_every_models_slot()
    tables = set(SQLModel.metadata.tables)
    offenders = sorted(tables - _owned_tables() - set(ALLOWLIST))
    assert not offenders, (
        f"table(s) {offenders} carry no user_id: add UserOwnedMixin to the model, "
        "or add the table to ALLOWLIST in this file with the reason it is not user-owned"
    )


def test_allowlist_names_only_tables_that_exist():
    _import_every_models_slot()
    stale = sorted(set(ALLOWLIST) - set(SQLModel.metadata.tables))
    assert not stale, f"ALLOWLIST names table(s) {stale} that no models slot defines — remove the rows"


def test_allowlist_does_not_shadow_an_owned_table():
    _import_every_models_slot()
    shadowed = sorted(set(ALLOWLIST) & _owned_tables())
    assert not shadowed, f"table(s) {shadowed} carry UserOwnedMixin; remove them from ALLOWLIST"
```

```bash
git rm -q server/tests/unit/models/test_tenant_tables.py
```

Integration tests — change each "another user's conversation" test to expect 404 (and drop nothing else yet; `org_id=` stays on the `User(...)` constructors until Task 4):

- `tests/integration/modules/conversation/test_dependencies.py`: rename `test_other_users_conversation_returns_403` → `test_other_users_conversation_returns_404`, docstring `"""Conversation exists but belongs to a different user → 404, as if missing."""`, assert `response.status_code == 404`. Replace `test_access_denied_error_code_in_response` with:

```python
    async def test_other_users_conversation_is_indistinguishable_from_a_missing_one(self, db_session, authenticated_client):
        """Same error code as a missing id, and no user id in the message."""
        other_user = User(
            clerk_id="clerk_access_other_2",
            org_id="test_org_123",
            email="access_other_2@example.com",
        )
        db_session.add(other_user)
        await db_session.flush()
        await db_session.refresh(other_user)

        other_conv = Conversation(user_id=other_user.id, name="Not Mine")
        db_session.add(other_conv)
        await db_session.flush()

        response = await authenticated_client.patch(
            f"/api/v1/conversation/conversation/{other_conv.id}/name",
            data={"name": "Hijack"},
        )
        data = response.json()
        assert response.status_code == 404
        assert data["error"] == "CONVERSATION_NOT_FOUND"
        assert str(other_user.id) not in response.text
```

- `tests/integration/modules/conversation/router/test_chatbot.py`: `test_chat_other_users_conversation_returns_403` → `..._returns_404`, assert 404.
- `tests/integration/modules/conversation/router/test_conversation.py`: `test_rename_other_users_conversation_returns_403` and `test_delete_other_users_conversation_returns_403` → `..._returns_404`, assert 404.
- `tests/integration/exceptions/test_handlers.py`: delete `test_access_denied_returns_403` (no `AuthorizationError` subclass remains to route through; the base mapping stays covered by `tests/unit/exceptions/test_exceptions.py`).

- [ ] **Step 2: Run them to verify they fail**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/models tests/integration/modules/conversation tests/integration/exceptions -v`
Expected: FAIL — `ImportError: cannot import name 'UserOwnedMixin'`; after that, the 404 assertions fail with 403.

- [ ] **Step 3: Implement**

`server/app/models/base.py` — replace `class TenantMixin` with:

```python
class UserOwnedMixin(SQLModel):
    """The owner column for a table whose rows belong to one user.

    The user is the tenant. A table that carries `user_id` is scoped by it in
    every query, and a lookup that finds another user's row answers 404, as for
    a row that does not exist. A table that does not carry it must be listed,
    with a reason, in tests/unit/models/test_owned_tables.py (architecture §9).
    """

    user_id: uuid.UUID = Field(foreign_key="user.id", index=True, nullable=False)
```

`server/app/modules/conversation/models.py`: import `UserOwnedMixin` from `app.models.base`; class header `class Conversation(BaseModel, UUIDPrimaryKeyMixin, UserOwnedMixin, SoftDeleteMixin, table=True):`; delete the `user_id: uuid.UUID = Field(...)` line (the mixin provides the identical column; keep the docstring's `user_id` attribute note). Remove `uuid` / `Field` imports only if ruff reports them unused.

`server/app/modules/conversation/dependencies.py` — the check becomes:

```python
    conversation = await conversation_service.get_conversation(db_session, conversation_id)

    # Another user's conversation answers exactly as a missing one, so an id
    # cannot be probed for existence (architecture/authorization.md).
    if not conversation or conversation.deleted_at is not None or conversation.user_id != user.id:
        raise ConversationNotFoundError(f"Conversation {conversation_id} not found", conversation_id=conversation_id)

    return conversation
```

Import only `ConversationNotFoundError`; docstring `Raises:` keeps only `ConversationNotFoundError: If the conversation is missing, deleted, or not the caller's`.

`server/app/modules/conversation/exceptions.py`: delete `class ConversationAccessDeniedError` and the `AuthorizationError` import if now unused.
`server/app/modules/conversation/__init__.py`: remove `ConversationAccessDeniedError` from the import and from `__all__`.

`.github/workflows/module-boundaries.yml:47`: `tests/unit/models/test_tenant_tables.py` → `tests/unit/models/test_owned_tables.py`.

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd server && make test && uv run ruff check . && uv run ruff format --check . && uv run lint-imports
cd .. && make gen-contract && git status --short server/openapi.json web-app/packages/api-client
```

Expected: all pass, including `test_migrations_produce_the_models_schema` (the conversation column is unchanged). `gen-contract` may change nothing; commit whatever it produces.

- [ ] **Step 5: Commit**

```bash
git add -A server .github web-app/packages/api-client
git commit -m "feat(server): user-owned tables and 404 for another user's conversation

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Remove organisations and roles from the server; one initial migration

**Files:**
- Delete: `server/app/modules/account/cache.py`, `server/alembic/versions/20260825_0900_b3f1c27a4e18_make_user_org_id_nullable.py`, `server/tests/unit/modules/account/test_cache.py`, `server/tests/unit/modules/account/test_dependencies.py`, `server/tests/integration/modules/account/test_dependencies.py`
- Modify: `server/app/api/middlewares/auth.py`, `server/app/modules/account/{__init__,dependencies,models,repository,service,webhooks}.py`, `server/app/modules/account/router/auth.py`, `server/app/integrations/clerk/{client.py,timestamps.py}`, `server/alembic/versions/20260411_1650_0c7838405158_initial_schema.py`
- Modify tests: `server/tests/unit/middleware/test_auth_middleware.py`, `server/tests/unit/modules/account/{test_models,test_service,test_repository,test_webhooks}.py`, `server/tests/unit/integrations/clerk/test_client.py`, `server/tests/integration/conftest.py`, `server/tests/unit/conftest.py`, `server/tests/integration/modules/account/{test_service,test_repository}.py`, `server/tests/integration/modules/account/router/{test_auth,test_auth_delete,test_webhooks}.py`, every integration test constructing `User(..., org_id=...)` (listed in Step 5)

**Interfaces:**
- Consumes: `UserOwnedMixin` (Task 3).
- Produces: `app.modules.account` exports exactly `CurrentUser`, `get_current_user`, `UserAlreadyExistsError`, `UserResponse`, `USER_ERASING`, `USER_SYNCED`, `router`, `user_service`. `UserService.resolve_user(session: AsyncSession, clerk_id: str) -> User`. `UserRepository.create(session, clerk_id, email, first_name=None, last_name=None, avatar_url=None, email_verified=False, last_synced_at=None) -> User` and `create_or_get` with the same parameters. `clerk_public_metadata(clerk_user: Any) -> dict` replaces `merge_clerk_metadata`. `User` has no `org_id`. `request.state` carries `clerk_id` and `user_id` only.

- [ ] **Step 1: Write the failing tests**

`server/tests/integration/modules/account/router/test_auth.py` — add at the end of the file (and `from unittest.mock import MagicMock, patch`, `from sqlalchemy import select`, `from app.modules.account.models import User` at the top):

```python
class TestGetMeWithoutOrganisation:
    """The user is the tenant: a token with no org claims is a full user."""

    @patch("app.modules.account.service.clerk_client.get_primary_email", return_value="no-org@example.com")
    @patch("app.modules.account.service.clerk_client.get_user")
    @patch("app.api.middlewares.auth.clerk_jwt_verifier")
    async def test_a_token_without_org_claims_provisions_the_user(
        self, mock_verifier, mock_get_user, _mock_email, client, db_session
    ):
        mock_verifier.verify_token.return_value = {"sub": "clerk_no_org_001"}
        clerk_user = MagicMock()
        clerk_user.first_name = "No"
        clerk_user.last_name = "Org"
        clerk_user.image_url = None
        clerk_user.primary_email_address_id = "email_1"
        clerk_user.updated_at = None
        clerk_user.public_metadata = {}
        mock_get_user.return_value = clerk_user

        response = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer t"})

        assert response.status_code == 200
        assert response.json()["email"] == "no-org@example.com"
        row = (await db_session.execute(select(User).where(User.clerk_id == "clerk_no_org_001"))).scalar_one()
        assert row.email == "no-org@example.com"
```

`server/tests/unit/middleware/test_auth_middleware.py` — `_make_app`'s endpoint returns:

```python
        return JSONResponse(
            {
                "clerk_id": getattr(request.state, "clerk_id", None),
                "user_id": getattr(request.state, "user_id", None),
                "state_keys": sorted(request.state._state),
            }
        )
```

Delete `test_org_claims_extracted_from_token`, `test_org_prefix_stripped`, `test_missing_org_claims_are_none` and the `# --- NEW: org claims ---` comment; add:

```python
    @pytest.mark.asyncio
    @patch("app.api.middlewares.auth.clerk_jwt_verifier")
    async def test_org_claims_are_ignored(self, mock_verifier, app):
        """A stale org claim sets nothing: the user is the tenant."""
        mock_verifier.verify_token.return_value = {
            "sub": "user_abc123",
            "o": {"id": "org_xyz", "rol": "org:admin"},
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/test", headers={"Authorization": "Bearer valid.token"})

        data = response.json()
        assert data["clerk_id"] == "user_abc123"
        assert data["state_keys"] == ["clerk_id", "user_id"]
```

`server/tests/integration/modules/account/test_service.py` — `existing_user` loses `org_id=`; `test_db_hit_returns_user_without_calling_clerk` calls `service.resolve_user(db_session, existing_user.clerk_id)`; delete `test_db_hit_syncs_org_id`; every `TestJITProvisioning` call becomes `service.resolve_user(db_session, clerk_id)` (two arguments).

- [ ] **Step 2: Run them to verify they fail**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/middleware tests/integration/modules/account/router/test_auth.py tests/integration/modules/account/test_service.py -v`
Expected: FAIL — `test_org_claims_are_ignored` sees `org_id`/`org_role` in `state_keys`; `resolve_user()` is missing `org_id`; the no-org HTTP test gets 401 (JIT raises "Organization membership required", which `get_current_user` wraps).

- [ ] **Step 3: Implement — middleware, dependencies, package surface, model**

`server/app/api/middlewares/auth.py`: docstring lists only `clerk_id : Clerk user ID (sub claim)` (keep the permissive note and the `user_id` note); `dispatch` initialises only `request.state.clerk_id = None` and `request.state.user_id = None`; inside `if payload:` keep only `request.state.clerk_id = payload.get("sub")` and `logger.debug("token_verified_in_middleware", clerk_id=request.state.clerk_id, path=request.url.path)`.

`server/app/modules/account/dependencies.py` — whole file:

```python
"""Account dependencies — who is calling.

The user is the tenant: there is no organisation and no role. Resource
ownership ("does this user own this conversation?") is checked in the owning
module's dependencies; nothing here touches a table but the user row.
"""

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import OAuth2AuthorizationCodeBearer

from app.core.config import settings
from app.core.logging import bind_context, logger
from app.database.dependencies import DbSession
from app.exceptions.base import AuthenticationError
from app.modules.account.models import User
from app.modules.account.service import user_service

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=settings.auth.AUTHORIZE_URL,
    tokenUrl=settings.auth.TOKEN_URL,
    scopes={
        "openid": "OpenID Connect",
        "profile": "Profile information",
        "email": "Email address",
        "offline_access": "Refresh token",
    },
    auto_error=False,
)


def get_clerk_id(request: Request) -> str:
    """Extract clerk_id from request.state (set by AuthMiddleware)."""
    clerk_id = getattr(request.state, "clerk_id", None)
    if not clerk_id:
        logger.error("clerk_id_not_in_request_state")
        raise AuthenticationError("Authentication required")
    return clerk_id


async def get_current_user(
    request: Request,
    session: DbSession,
    clerk_id: str = Depends(get_clerk_id),
    _token: str = Depends(oauth2_scheme),
) -> User:
    """Get the current authenticated user with JIT provisioning."""
    try:
        user = await user_service.resolve_user(session, clerk_id)
        request.state.user_id = user.id
        bind_context(user_id=user.id)
    except Exception as e:
        logger.error("user_provisioning_failed", clerk_id=clerk_id, error=str(e))
        raise AuthenticationError("Failed to provision user") from e
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
```

`server/app/modules/account/__init__.py` — whole file:

```python
"""Account — the Clerk-backed identity: the user row, the caller's identity, erasure.

This is the public surface. Another module imports from here and nowhere
deeper (docs/architecture/server.md, R1).

The dependency getter is exported alongside its Annotated alias on purpose:
FastAPI keys dependency_overrides by the exact callable, so get_current_user
is the only way a test can stand in for CurrentUser.
"""

from app.modules.account.dependencies import CurrentUser, get_current_user
from app.modules.account.exceptions import UserAlreadyExistsError
from app.modules.account.router import router
from app.modules.account.schemas import UserResponse
from app.modules.account.service import USER_ERASING, USER_SYNCED, user_service

__all__ = [
    "CurrentUser",
    "USER_ERASING",
    "USER_SYNCED",
    "UserAlreadyExistsError",
    "UserResponse",
    "get_current_user",
    "router",
    "user_service",
]
```

`server/app/modules/account/models.py`: module docstring `"""The user row."""`; delete the `org_id` attribute from the class docstring and the `org_id: Optional[str] = Field(default=None, index=True)` field; delete `self.org_id = None` from `anonymize_user`; delete `class Role` and the `StrEnum` import.

```bash
git rm -q server/app/modules/account/cache.py
```

- [ ] **Step 4: Implement — service, repository, webhooks, router, Clerk client, migration**

`server/app/modules/account/service.py`:
- Module docstring: `"""User service with JIT provisioning."""`.
- Imports: delete `AuthorizationError`, `user_cache`, `MISS`, and `Optional` if unused.
- Delete `USER_OFFBOARDED`.
- Replace `merge_clerk_metadata` with:

```python
def clerk_public_metadata(clerk_user: Any) -> dict:
    """A Clerk user's public metadata as a plain dict; empty if it carries none."""
    metadata = getattr(clerk_user, "public_metadata", None) or {}
    return dict(metadata) if isinstance(metadata, dict) else {}
```

- `resolve_user`:

```python
    @staticmethod
    async def resolve_user(session: AsyncSession, clerk_id: str) -> User:
        """Resolve the current user by clerk_id, JIT-provisioning if needed.

        Args:
            session: Database session for DB operations.
            clerk_id: The Clerk user ID.

        Returns:
            The User object (attached to the current session).

        Raises:
            RuntimeError: If user cannot be provisioned from Clerk.
            UserAlreadyExistsError: A genuine (non-race) unique constraint
                conflict during provisioning — see UserRepository.create_or_get.
        """
        # 1. Look up by clerk_id (unique + indexed -> single index scan).
        #    There is deliberately no clerk_id -> user_id cache: a hit would
        #    still cost one indexed lookup, and FastAPI's per-request Depends
        #    cache already prevents repeat resolution within a request.
        user = await user_repository.get_by_clerk_id(session, clerk_id)
        if user:
            return user

        # 2. JIT: Fetch from Clerk and create in DB
        logger.info("jit_provisioning_user", clerk_id=clerk_id)

        try:
            clerk_user = await asyncio.to_thread(clerk_client.get_user, clerk_id)
        except ClerkUserNotFoundError:
            logger.error("clerk_user_not_found_during_provisioning", clerk_id=clerk_id)
            raise

        email = clerk_client.get_primary_email(clerk_user)

        if not email:
            logger.error("clerk_user_missing_email", clerk_id=clerk_id)
            raise RuntimeError(f"No email found for Clerk user {clerk_id}")

        user = await user_repository.create_or_get(
            session=session,
            clerk_id=clerk_id,
            email=email,
            first_name=clerk_user.first_name,
            last_name=clerk_user.last_name,
            avatar_url=clerk_user.image_url,
            email_verified=bool(clerk_user.primary_email_address_id),
            last_synced_at=clerk_timestamp_to_datetime(getattr(clerk_user, "updated_at", None)),
        )

        await events.publish(USER_SYNCED, session=session, user_id=user.id, metadata=clerk_public_metadata(clerk_user))

        return user
```

- Delete `resolve_org_role`.
- `erase_user`: delete `original_clerk_id = user.clerk_id` and `await user_cache.invalidate_user(clerk_id=original_clerk_id)`; in the docstring delete the two sentences beginning "The org-role cache is invalidated last".

`server/app/modules/account/repository.py`: remove the `org_id` parameter from `create` and `create_or_get` (signature, docstring paragraph about `org_id`, the `User(org_id=...)` kwarg, the pass-through, and `org_id=org_id` in the `user_created` log); delete `update_org_id`.

`server/app/modules/account/webhooks.py`:
- Module docstring lines 14-19 become: `Ordering: Clerk guarantees none. The user.* handlers compare the payload's` / `\`updated_at\` against \`User.last_synced_at\` and drop the stale one.`
- Imports: delete `user_cache`; `from app.modules.account.service import USER_SYNCED, user_service`.
- `handle_user_created` docstring: replace the first two paragraphs with:

```
    Sign-up is public and every Clerk user is a customer, so the row is
    created unconditionally — the same row JIT provisioning would create at
    the user's first request.
```

  and delete `org_id=None,` from the `create_or_get` call.
- Delete `_organization_id`, `_resolve_or_create_user`, `_sync_org_and_invalidate`, `handle_membership_created`, `handle_membership_updated`, `handle_membership_deleted`, and the comment + `for _prefix in (...)` registration loop at the bottom. The three `clerk_dispatcher.register("user.*", ...)` lines stay.

`server/app/integrations/clerk/timestamps.py` lines 11 and 18: delete the references to membership handlers (UNSYNCED_EPOCH now serves `handle_user_created` only).

`server/app/integrations/clerk/client.py`: delete `get_first_org_membership` (lines 138-182); in the `get_user` comment at line 44, drop the clause about `get_organization_memberships`.

`server/app/modules/account/router/auth.py` `delete_me` docstring: delete step `6. Invalidate the org-role cache`.

Migration — one initial revision:

```bash
git rm -q server/alembic/versions/20260825_0900_b3f1c27a4e18_make_user_org_id_nullable.py
```

In `server/alembic/versions/20260411_1650_0c7838405158_initial_schema.py` delete `sa.Column("org_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),`, `op.create_index(op.f("ix_user_org_id"), "user", ["org_id"], unique=False)` and `op.drop_index(op.f("ix_user_org_id"), table_name="user")`.

- [ ] **Step 5: Update the remaining tests**

Delete:

```bash
git rm -q server/tests/unit/modules/account/test_cache.py \
          server/tests/unit/modules/account/test_dependencies.py \
          server/tests/integration/modules/account/test_dependencies.py
```

Edit:
- `tests/unit/conftest.py`, `tests/integration/conftest.py`: delete the autouse `clear_user_cache` fixture (nothing left to clear). `tests/integration/conftest.py` `test_user` loses `org_id="test_org_123",`. `tests/README.md`: delete the `clear_user_cache` rows.
- Remove `org_id="test_org_123",` (or `org_id=...`) from every `User(...)` in: `tests/integration/modules/conversation/{test_repository,test_service,test_dependencies}.py`, `tests/integration/modules/conversation/router/{test_chatbot,test_conversation}.py`, `tests/integration/database/test_dependencies.py:94`, `tests/integration/modules/account/test_repository.py` (fixture and every `create` / `create_or_get` call).
- `tests/integration/modules/account/test_repository.py`: delete `class TestUpdateOrgId`.
- `tests/integration/modules/account/router/test_auth_delete.py`: delete `class TestDeleteMeCacheInvalidation`'s cache tests (`test_clears_the_role_cache`, `test_uses_pre_anonymisation_clerk_id`, `test_unrelated_users_are_untouched`) and `test_org_id_is_cleared`, plus the `user_cache` / `MISS` imports; keep every test about the Clerk delete, the 204 and anonymisation. If the class is left empty, delete it.
- `tests/integration/modules/account/router/test_webhooks.py`: delete `MEMBERSHIP_DATA` and every test that posts an `organization_membership.*` / `organizationMembership.*` event (`test_membership_before_create_leaves_correct_state`, `test_membership_deleted_clears_org`, `test_membership_deleted_for_different_org_leaves_state_intact`, and the membership half of `test_create_declines_when_clerk_no_longer_has_the_user`); delete the `org_id` assertions in `test_user_created_persists_the_row` and `test_user_deleted_anonymises_and_replay_is_a_noop`; drop "organizationMembership" from the `clerk_has_the_user` docstring. Add:

```python
async def test_membership_events_are_acknowledged_and_ignored(client, db_session):
    """The app has no organisations: a membership event is an unregistered type."""
    response = await post(client, "organizationMembership.created", {"id": "orgmem_1"})
    assert response.status_code == 204
```

  (`post` is the module-level helper already defined in this file; the dispatcher logs and ignores unregistered types with a 204, as `test_unknown_event_type_returns_204` shows.)
- `tests/unit/modules/account/test_models.py`: delete `class TestRole`.
- `tests/unit/modules/account/test_service.py`: `make_user()` loses `org_id`; in the six `test_erase_user_*` tests delete the `user_cache.invalidate_user` patch and its assertions, delete `test_erase_user_invalidates_with_pre_anonymisation_clerk_id`, and delete the `assert user.org_id is None` line; replace the three `merge_clerk_metadata` tests and `FakeMembership` with:

```python
def test_public_metadata_is_returned_as_a_dict():
    assert clerk_public_metadata(SimpleNamespace(public_metadata={"plan": "free"})) == {"plan": "free"}


def test_public_metadata_tolerates_missing_and_malformed_values():
    assert clerk_public_metadata(SimpleNamespace()) == {}
    assert clerk_public_metadata(SimpleNamespace(public_metadata=None)) == {}
    assert clerk_public_metadata(SimpleNamespace(public_metadata="not-a-dict")) == {}
```

  (import `clerk_public_metadata` from `app.modules.account.service` and `SimpleNamespace` from `types`).
- `tests/unit/modules/account/test_repository.py`: drop `org_id=` arguments; delete `test_create_accepts_a_null_org_id`.
- `tests/unit/modules/account/test_webhooks.py`: delete `MEMBERSHIP_PAYLOAD`, the `USER_OFFBOARDED` and membership-handler imports, `test_no_handler_populates_the_role_cache`, and every membership test (the 17 listed under "membership" in the handler section: `test_created_*`, `test_updated_*`, `test_deleted_*`, `test_both_event_spellings_dispatch`, `test_deleted_for_unknown_user_is_a_noop`); `existing_user()` / `make_user()` lose `org_id`; `test_user_created_inserts_with_null_org_and_clerk_timestamp` → `test_user_created_inserts_with_clerk_timestamp` and drop its `org_id` assertion.
- `tests/unit/integrations/clerk/test_client.py`: delete `class TestGetFirstOrgMembership` and the `get_organization_memberships` mention in `_client_returning`'s docstring.

- [ ] **Step 6: Run everything**

```bash
cd server
make test
uv run ruff check . && uv run ruff format --check . && uv run lint-imports
cd .. && make gen-contract && make check-contract
git grep -n -E "org_id|org_role|organization|Organisation|organisation|TenantMixin|require_role|CurrentRole|CurrentOrgId|USER_OFFBOARDED|user_cache|project_manager|reviewer|approver|supplier" -- server/app server/tests server/alembic
```

Expected: all green, including `test_migrations_produce_the_models_schema` and the new no-org test. The grep returns nothing except the word "organisation" in the middleware/dependency docstrings that say there is none — read each hit and confirm. If an existing dev database is stamped at `b3f1c27a4e18`, reset it: `make docker-stop`, `docker volume rm personal-finance_postgres-data` (check the exact name with `docker volume ls`), then `make docker-run-db ENV=development` and `make -C server migrate ENV=development`.

- [ ] **Step 7: Commit**

```bash
git add -A server web-app/packages/api-client
git commit -m "feat(server): the user is the tenant — no organisations, no roles

Drops org_id, the role guards, the org-role cache and the membership
webhooks. One initial migration.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Remove organisations and roles from the web app; public sign-up

**Files:**
- Delete: `web-app/packages/auth/src/permissions.ts`, `web-app/packages/auth/src/permissions.test.ts`, `web-app/apps/internal-portal/src/app/unauthorized/`, `web-app/apps/internal-portal/src/app/(dashboard)/orders/`, `web-app/apps/internal-portal/src/app/(dashboard)/projects/`
- Create: `web-app/apps/internal-portal/src/app/(auth)/sign-up/[[...sign-up]]/page.tsx`
- Modify: `web-app/packages/auth/src/{index.ts,provider.tsx,provider.test.tsx}`, `web-app/packages/components/src/layout/{user-panel.tsx,user-panel.test.tsx}`, `web-app/apps/internal-portal/src/{proxy.ts, lib/hub-nav.ts, components/layout/clerk-user-panel.tsx, components/layout/clerk-user-panel.test.tsx}`, `web-app/apps/internal-portal/.env.example`, `web-app/Dockerfile`, `docker-compose.dev.yml`, `docker-compose.prod.yml`

**Interfaces:**
- Produces: `@app/auth` exports `AuthProvider`, `useAppAuth`, `AppUser` only; `useAppAuth()` returns `{ user, isLoaded, getToken, signOut }`. `UserDetailsPanel` props are `{ user, onSignOut, onOpenProfile? }`.

- [ ] **Step 1: Write the failing tests**

`clerk-user-panel.test.tsx`: delete `import { Role } from "@app/auth"`, the `openOrganizationProfile` mock, `role: Role.REVIEWER` in `setAuth`, the comment `// Role stays real; only the hook is replaced.`, and both Organisation tests (`offers Organisation to a project manager`, the `it.each` "does not offer Organisation"); the `vi.mock("@app/auth", ...)` becomes `vi.mock("@app/auth", () => ({ useAppAuth: () => mocks.auth }))`. Add:

```tsx
  it("never offers Organisation", async () => {
    setAuth()
    renderPanel()
    await openMenu(/Ada Lovelace/)

    await screen.findByRole("menuitem", { name: /Log out/ })
    expect(
      screen.queryByRole("menuitem", { name: /Organisation/ }),
    ).not.toBeInTheDocument()
  })
```

`user-panel.test.tsx`: delete `offers Organisation alone when given only onOpenOrganizationProfile`, and delete the `Organisation`-absence assertions in the two other tests.

`provider.test.tsx`: delete `orgRole` from the hoisted Clerk mock state, from the mocked `useAuth` return, and from `beforeEach`; delete `describe("role", ...)`. Add inside the existing `describe("user", ...)` block:

```tsx
    it("exposes no role", () => {
      expect(renderAuth().current).not.toHaveProperty("role")
    })
```

```bash
git rm -q web-app/packages/auth/src/permissions.ts web-app/packages/auth/src/permissions.test.ts
```

- [ ] **Step 2: Run them to verify they fail**

Run: `make test-web`
Expected: FAIL — `exposes no role` (the provider still returns `role`), and imports of `./permissions` in `index.ts` / `provider.tsx` no longer resolve.

- [ ] **Step 3: Implement — auth package and user panel**

`web-app/packages/auth/src/index.ts`:

```ts
export { AuthProvider, useAppAuth, type AppUser } from "./provider"
```

`web-app/packages/auth/src/provider.tsx`: header comment line 4 → `* Portability seam: AuthProvider wraps Clerk's hooks to derive identity.`; delete `import { getUserRole, Role } from "./permissions"`; delete the `role` member (and its doc comment) from `AuthContextValue` and `role: null` from the default context; `const { isLoaded, getToken, signOut: endSession } = useAuth()`; delete `const role = getUserRole(orgRole)`; provider value `{ user, isLoaded, getToken, signOut }`; hook doc → `Hook for the current user's identity.` / `Never call useAuth() or useUser() directly in a component, and check isLoaded before rendering user-dependent UI.`

`web-app/packages/components/src/layout/user-panel.tsx`: drop `Building2` from the lucide import and `onOpenOrganizationProfile` from `UserDetailsPanelProps` and the destructuring; replace the two `(onOpenProfile || onOpenOrganizationProfile) && ...` blocks with:

```tsx
          {onOpenProfile && (
            <>
              <DropdownMenuGroup>
                <DropdownMenuItem
                  className="cursor-pointer"
                  onClick={onOpenProfile}
                >
                  <BadgeCheck />
                  Account
                </DropdownMenuItem>
              </DropdownMenuGroup>
              <DropdownMenuSeparator />
            </>
          )}
```

`web-app/apps/internal-portal/src/components/layout/clerk-user-panel.tsx`:

```tsx
"use client"

import { useClerk } from "@clerk/nextjs"
import { useAppAuth } from "@app/auth"
import { UserDetailsPanel } from "@app/components/layout/user-panel"

export function ClerkUserPanel() {
  const { isLoaded, user, signOut } = useAppAuth()
  const { openUserProfile } = useClerk()

  return (
    <UserDetailsPanel
      user={
        isLoaded && user
          ? {
              name: user.name ?? "User",
              email: user.email ?? "No email",
              imageUrl: user.imageUrl ?? undefined,
            }
          : null
      }
      onSignOut={() => void signOut()}
      onOpenProfile={() => openUserProfile()}
    />
  )
}
```

- [ ] **Step 4: Implement — routing, sign-up, nav, build args**

`web-app/apps/internal-portal/src/proxy.ts`:

```ts
import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server"
import { NextResponse } from "next/server"

// Sign-up is public: anyone may create an account, and their first request
// provisions it. Every other route needs a session.
const isPublicRoute = createRouteMatcher(["/sign-in(.*)", "/sign-up(.*)"])

export default clerkMiddleware(async (auth, req) => {
  // `/` is an alias for `/home`, and the redirect has to happen here rather
  // than in an `app/page.tsx` calling redirect(). A page-level redirect reaches
  // a client-side navigation as a flight-stream error, not an HTTP redirect,
  // and the App Router deadlocks on one during the transition that follows
  // Clerk's setActive() — blank page, URL stuck on `/`, recoverable only by a
  // manual reload. Redirecting before auth.protect() also keeps `/` out of the
  // ?redirect_url= that a bounced visitor carries into sign-in, so they come
  // back to `/home` directly instead of through `/`.
  if (req.nextUrl.pathname === "/") {
    return NextResponse.redirect(new URL("/home", req.url))
  }

  if (isPublicRoute(req)) return

  await auth.protect()
})

export const config = {
  matcher: [
    // Skip Next.js internals and all static files, unless found in search params
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    // Always run for API routes
    "/(api|trpc)(.*)",
  ],
}
```

Create `web-app/apps/internal-portal/src/app/(auth)/sign-up/[[...sign-up]]/page.tsx`:

```tsx
import { SignUp } from "@clerk/nextjs"

export default function SignUpPage() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <SignUp />
    </div>
  )
}
```

```bash
git rm -r -q "web-app/apps/internal-portal/src/app/unauthorized" \
  "web-app/apps/internal-portal/src/app/(dashboard)/orders" \
  "web-app/apps/internal-portal/src/app/(dashboard)/projects"
```

`web-app/apps/internal-portal/src/lib/hub-nav.ts`:

```ts
"use client"

import { HomeIcon } from "lucide-react"
import type { NavItem } from "@app/core/types/nav"

/**
 * The sidebar's entries. Finance pages add theirs here.
 */
export const HUB_NAV: NavItem[] = [{ title: "Home", url: "/home", icon: HomeIcon }]
```

`web-app/apps/internal-portal/.env.example` — after the sign-in fallback line append:

```
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up
NEXT_PUBLIC_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL=/home
```

Add the same two lines to your local `.env.local`.

`web-app/Dockerfile` builder stage, after the `NEXT_PUBLIC_CLERK_SIGN_IN_URL` pair:

```dockerfile
ARG NEXT_PUBLIC_CLERK_SIGN_UP_URL
ENV NEXT_PUBLIC_CLERK_SIGN_UP_URL=$NEXT_PUBLIC_CLERK_SIGN_UP_URL
```

Both compose files, web service `build.args`, after `NEXT_PUBLIC_CLERK_SIGN_IN_URL`:

```yaml
        NEXT_PUBLIC_CLERK_SIGN_UP_URL: ${NEXT_PUBLIC_CLERK_SIGN_UP_URL:-/sign-up}
```

- [ ] **Step 5: Verify**

```bash
make test-web
make check-web
cd web-app && pnpm type-check && pnpm --filter internal-portal build && cd ..
git grep -n -E "orgRole|Organization|Organisation|getUserRole|isInternalRole|isSupplierRole|ROLE_LABELS|Role\.|unauthorized" -- web-app/apps web-app/packages ':!**/generated/**'
```

Expected: tests, lint, types and build pass; the grep returns only the "never offers Organisation" test.

- [ ] **Step 6: Commit**

```bash
git add -A web-app docker-compose.dev.yml docker-compose.prod.yml
git commit -m "feat(web): no organisations or roles; public sign-up

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Clerk — config, scripts, and the existing instance

**Files:**
- Delete: `scripts/clerk/apply-roles.sh`
- Modify: `scripts/clerk/{config.json, apply-config.sh, pull-config.sh, check-config.sh, seed-users.sh, bootstrap-env.sh}`, `server/data/clerk-dev-seed.json`, `Makefile` (Clerk help lines 66-75 and targets 229-260)

**Interfaces:**
- Produces: `make clerk-setup` = bootstrap-env (skipped when `CLERK_APP_ID` is set) → apply-config → seed-users. Seed users `dev-alice@example.com`, `dev-bob@example.com`.

- [ ] **Step 1: [USER] Pull the live instance config and diff it**

```bash
make clerk-pull-config
git diff scripts/clerk/config.json
```

Show the diff to the user. Every instance setting that is not about organisations or roles (social providers, password rules, name fields, verification strategies) is **kept as pulled** — that is the instance's real state. Then `git checkout -- scripts/clerk/config.json` only if the user says the template's values should win.

- [ ] **Step 2: Edit config.json**

Starting from the pulled file:
- `"auth_access_control": { "sign_up_mode": "public" }`
- `"organization_settings": { "enabled": false }` (delete `admin_delete_enabled`, `force_organization_selection`, `slug_disabled`).
- Delete the `"x_organization_roles"` key entirely.

- [ ] **Step 3: Scripts**

```bash
git rm -q scripts/clerk/apply-roles.sh
```

`apply-config.sh`: header lines 5-6 → `# alone.`; replace lines 34-37 with:

```bash
echo "==> Applying $BASELINE"
clerk config patch --app "$CLERK_APP_ID" --instance dev --file "$BASELINE" --yes "$@"
```

(delete the `PATCH` temp-file variable and its cleanup if nothing else uses them); line 43 → `echo "Next: 'make clerk-seed-users'."`.

`pull-config.sh`: delete the header lines 14-16 about `x_organization_roles`, the `--full` help's "plus the roles", the roles block (lines 56-69), and the three `x_organization_roles` merges (lines 72, 85, 95) — the pulled config is the instance config, trimmed to the existing key set.

`check-config.sh`: header lines 8-10 → `# HIBP check refuses seeded passwords at sign-in, which looks like a credentials` / `# bug rather than a configuration one.`; delete lines 20-21; line 57 → `    echo "    git checkout -- $BASELINE && make clerk-apply-config"`.

`bootstrap-env.sh`: line 33 → `echo "run 'make clerk-apply-config', 'make clerk-seed-users'."`; lines 103-105 →

```bash
echo "  make clerk-apply-config    instance settings"
echo "  make clerk-seed-users      two dev users"
```

`seed-users.sh`: replace the header (lines 2-22) with:

```bash
# Create the dev users in the Clerk development instance.
#
# server/data/clerk-dev-seed.json is COMMITTED ON PURPOSE: fake emails,
# throwaway passwords, and a guard that refuses anything but a development
# instance. Users created through the Backend API are email-verified on
# creation, and skip_password_checks lets them carry those passwords.
#
# Two ordinary users, so isolation can be checked by hand: what one creates,
# the other must never see.
#
# Idempotent. Existing users and their passwords are left alone.
#
# Needs 'make clerk-apply-config' (password sign-in, HIBP off at sign-in) first.
```

Delete the "Checking the roster's roles exist" block (lines 55-61), the `IDS` bookkeeping, and the Organization and Memberships sections (lines 97-138). The users loop becomes:

```bash
echo "==> Users"
users_created=0; users_unchanged=0
while IFS= read -r entry; do
  email="$(jq -r '.email' <<< "$entry")"
  # GET /users returns a bare array; tolerate {data:[...]} too.
  user_id="$(api "/users?email_address=$(jq -rn --arg e "$email" '$e|@uri')" \
    | jq -r 'if type == "array" then . else (.data // []) end | .[0].id // empty')"
  if [ -z "$user_id" ]; then
    api /users -X POST -d "$(jq -c '{
      email_address: [.email],
      password,
      first_name,
      last_name,
      skip_password_checks: true,
      skip_restriction_checks: true
    }' <<< "$entry")" > /dev/null
    echo "    created   $email"
    users_created=$(( users_created + 1 ))
  else
    echo "    unchanged $email"
    users_unchanged=$(( users_unchanged + 1 ))
  fi
done < <(jq -c '.users[]' "$ROSTER")

echo
echo "PASS: users $users_created created, $users_unchanged unchanged."
echo
echo "Sign in on the web app (http://localhost:3000) as either of them;"
echo "the passwords are in $ROSTER."
```

`server/data/clerk-dev-seed.json`:

```json
{
  "users": [
    {
      "email": "dev-alice@example.com",
      "password": "personal-finance-dev-alice-5d2c",
      "first_name": "Alice",
      "last_name": "Dev"
    },
    {
      "email": "dev-bob@example.com",
      "password": "personal-finance-dev-bob-8e17",
      "first_name": "Bob",
      "last_name": "Dev"
    }
  ]
}
```

- [ ] **Step 4: Makefile**

- Help: delete the `clerk-apply-roles` line; `clerk-setup` → `- The next three, in order; a re-run skips creating the app`; `clerk-seed-users` → `- Create the dev users in server/data/clerk-dev-seed.json`.
- `clerk-setup` recipe: delete `@./scripts/clerk/apply-roles.sh`; comment line → `# clerk-setup runs the scripts, not the targets: under -j prerequisites run in` / `# parallel, and seeding needs the applied config.`
- Delete the `clerk-apply-roles:` target and drop it from `.PHONY`.

- [ ] **Step 5: Static checks**

```bash
bash -n scripts/clerk/*.sh
jq -e '.organization_settings.enabled == false and (has("x_organization_roles") | not) and .auth_access_control.sign_up_mode == "public"' scripts/clerk/config.json
jq -e '.users | length == 2 and all(has("role") | not)' server/data/clerk-dev-seed.json
git grep -n -i -E "organization|apply-roles|x_organization|role" -- scripts/clerk Makefile server/data
```

Expected: syntax OK, both `jq -e` print `true`, the grep returns nothing (or only `organization_settings` in config.json).

- [ ] **Step 6: [CONFIRM] Apply to the instance and seed**

Ask the user, then:

```bash
make clerk-apply-config
make clerk-check-config     # must report no drift
make clerk-seed-users
```

- [ ] **Step 7: [USER] Dashboard steps no API covers**

1. **Webhooks → Add endpoint**: `https://<NGROK_DOMAIN>/api/v1/webhooks/clerk`, events `user.created`, `user.updated`, `user.deleted` only. Copy its signing secret into `CLERK_WEBHOOK_SIGNING_SECRET` in `server/.env.development`.
2. **OAuth application** (the legacy Swagger client): add redirect URI `http://localhost:8100/docs/oauth2-redirect`; keep the legacy `:8000` one until cutover.
3. **Account Portal → Sign-up** page enabled.

- [ ] **Step 8: Commit**

```bash
git add -A scripts/clerk server/data Makefile
git commit -m "chore(clerk): public sign-up, no organisations, two dev users

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Identity — Personal Finance, apps/web, WEB_* names

**Files:**
- Move: `web-app/apps/internal-portal/` → `web-app/apps/web/`; `template-app.code-workspace` → `personal-finance.code-workspace`
- Modify: `server/pyproject.toml:7,109` (+ `title`/`description` in `[tool.app.metadata]`), `server/.env.example:6`, `server/scripts/docker-image-name.sh:33`, `server/Makefile:10`, `server/scripts/compose-env.sh:33-34`, `Makefile`, `.env.example`, both compose files, `web-app/{Dockerfile,package.json,vitest.config.mts}`, `web-app/apps/web/{package.json, src/app/layout.tsx, src/app/(dashboard)/layout.tsx}`, `scripts/worktree/{init,clean}.sh`, `scripts/deploy-check.sh`, `scripts/clerk/{bootstrap-env,bootstrap-oauth}.sh`, `.vscode/{settings,tasks}.json`, `server/openapi.json` + generated client (regenerated)

**Interfaces:**
- Produces: compose service `web`, image `${COMPOSE_PROJECT_NAME}-web`, Make target `dev-web`, VS Code task `Dev: Web`, variables `WEB_HOST_PORT` (default 3000) and `WEB_DOMAIN`. Traefik routers `${COMPOSE_PROJECT_NAME}-web-web` (HTTP entrypoint) and `${COMPOSE_PROJECT_NAME}-web-secure`, service `${COMPOSE_PROJECT_NAME}-web` — the existing `<service>-<entrypoint>` scheme.

- [ ] **Step 1: Move the app**

```bash
git mv web-app/apps/internal-portal web-app/apps/web
mv web-app/apps/internal-portal/.env.local web-app/apps/web/.env.local 2>/dev/null || true
rm -rf web-app/apps/internal-portal
git mv template-app.code-workspace personal-finance.code-workspace
```

- [ ] **Step 2: Mechanical renames**

Apply these replacements in exactly these files (use an editor or `perl -pi -e`; BSD `sed -i` needs `''`):

| From | To | Files |
|---|---|---|
| `apps/internal-portal` | `apps/web` | `Makefile`, `server/Makefile`, `server/scripts/compose-env.sh`, both compose files, `web-app/Dockerfile`, `scripts/worktree/init.sh`, `scripts/deploy-check.sh`, `scripts/clerk/bootstrap-env.sh`, `.vscode/settings.json` |
| `internal-portal` (service, filter, image, app names) | `web` | `Makefile`, both compose files, `web-app/package.json`, `web-app/vitest.config.mts`, `scripts/worktree/clean.sh`, `scripts/deploy-check.sh`, `.vscode/tasks.json` |
| `INTERNAL_PORTAL_HOST_PORT` | `WEB_HOST_PORT` | `Makefile`, `.env.example`, `docker-compose.dev.yml`, `scripts/worktree/{init,clean}.sh`, your local `.env` |
| `INTERNAL_PORTAL_DOMAIN` | `WEB_DOMAIN` | `docker-compose.prod.yml`, `scripts/deploy-check.sh` |
| `dev-internal` / `dev:internal` | `dev-web` / `dev` | `Makefile`, `web-app/package.json`, `.vscode/tasks.json`, `scripts/worktree/init.sh` |
| `BASE_INTERNAL` / `INTERNAL_PORT` | `BASE_WEB` / `WEB_PORT` | `scripts/worktree/init.sh` |
| `"Dev: Internal Portal"` | `"Dev: Web"` | `.vscode/tasks.json` |
| `Internal Portal:` (Makefile echo) | `Web app:` | `Makefile` |

Then by hand:
- `web-app/package.json`: `"dev": "pnpm --filter web dev",` (one dev script).
- `web-app/apps/web/package.json`: `"name": "@app/web",`.
- `docker-compose.prod.yml` `WEB_DOMAIN` guard text: `${WEB_DOMAIN:?set to the web app hostname, e.g. app.example.com}`.
- `scripts/deploy-check.sh`: `export WEB_DOMAIN="${WEB_DOMAIN:-web.localhost}"`.

- [ ] **Step 3: Identity strings**

- `server/pyproject.toml`: `[project] description = "Personal Finance Server - the API behind the Personal Finance app"`; `[tool.app.metadata] title = "Personal Finance - Server"`; set its `description` to `"API for Personal Finance: transactions, analytics and insights for one user's money."`.
- `server/.env.example:6`: `PROJECT_NAME="Personal Finance Server"` (and local env files).
- `server/scripts/docker-image-name.sh:33`: fallback `personal-finance-server`.
- `Makefile:39-40`: `CLERK_APP_NAME ?= Personal Finance Dev` and its comment example `"Personal Finance Dev — <name>"`.
- `scripts/clerk/bootstrap-env.sh:20,108`: `Personal Finance Dev`.
- `scripts/clerk/bootstrap-oauth.sh:46`: `Personal Finance Swagger Docs`.
- `personal-finance.code-workspace`: folder name `"personal-finance"`.
- `web-app/apps/web/src/app/layout.tsx` metadata: `title: "Personal Finance"`, `description: "Personal Finance — track your spending, understand where it goes, and save more."`. Keep only the icon entry whose file exists (`/icons/favicon.ico`); delete the three that point at missing files.
- `web-app/apps/web/src/app/(dashboard)/layout.tsx`: `logoAlt="Personal Finance"`.
- Branding: the legacy logo and favicon are byte-identical to the template's — verify with `cmp ../pf-legacy/web-app/public/images/logo-small.png web-app/apps/web/public/images/logo-small.png && cmp ../pf-legacy/web-app/public/icons/favicon.ico web-app/apps/web/public/icons/favicon.ico`; copy only if `cmp` reports a difference.

- [ ] **Step 4: Regenerate and verify**

```bash
cd web-app && pnpm install && cd ..
make gen-contract
make check-contract
make test-web && make check
cd web-app && pnpm type-check && pnpm --filter web build && cd ..
make -C server test
bash scripts/verify-infra.sh
make deploy-check
git grep -n -i -E "internal-portal|internal_portal|INTERNAL_PORTAL|dev-internal|dev:internal|template app|template-app|template server|template dev" -- . ':!docs' ':!.claude' ':!.superpowers' ':!**/README.md' ':!**/CLAUDE.md' ':!CLAUDE.md'
```

Expected: all pass; `server/openapi.json` title is "Personal Finance - Server" and every generated client file header follows; the grep returns nothing.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: rename to Personal Finance; internal-portal becomes apps/web

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Architecture, setup and service docs

Every statement below must match the code after Tasks 1–7. The architecture-doc rule (`docs/README.md` §Architecture): state facts — no decisions, rejected alternatives or history.

**Files:**
- Delete: `docs/setup/making-it-yours.md`
- Rewrite: `docs/architecture/authorization.md`, `docs/setup/clerk.md`, `web-app/apps/web/README.md`, `README.md`, `web-app/README.md`
- Edit: `docs/architecture/{authentication,server,web-app}.md`, `docs/setup/{infrastructure,deploy-dokploy}.md`, `docs/guides/api-client-codegen.md`, `docs/README.md`, `docs/data-model/{README,account,conversation}.md`, `CLAUDE.md`, `server/CLAUDE.md`, `web-app/CLAUDE.md`, `server/README.md`, `server/docs/{authentication,gdpr-compliance-guide,gdpr-erasure-findings}.md`

- [ ] **Step 1: Salvage, then delete making-it-yours.md**

Move two facts into `README.md` under a short "Identity" subsection: (1) `server/pyproject.toml [tool.app.metadata]` is the service's public identity, and changing it is a contract change — run `make gen-contract` in the same commit; (2) `COMPOSE_PROJECT_NAME` names the compose project, image tags and Traefik labels, while `PROJECT_NAME` only tags the server image built by `make -C server docker-build`. Then `git rm docs/setup/making-it-yours.md` and fix its inbound links (`docs/BUGS.md`, `README.md`, `server/README.md`, `docs/product/README.md`, `docs/product/features/account.md`, `docs/architecture/authorization.md`, `docs/setup/clerk.md`) — `git grep -n making-it-yours` must return nothing.

- [ ] **Step 2: authorization.md — rewrite (target ≤ 60 lines)**

Sections: **1. The model** — the user is the tenant; there are no organisations and no roles; every signed-in user is equal. **2. From token to decision** — diagram: `sub → request.state.clerk_id` (AuthMiddleware, never blocks) → `CurrentUser` (401 without a valid token; JIT-provisions the row) → ownership dependency in the owning module (e.g. `UserConversation`): missing, soft-deleted or another user's row → **404** with the module's not-found code. **3. Where each rule is enforced** — server: `CurrentUser` on every non-public route, repository queries filter by `user_id`, ownership dependencies for single-row lookups; web: `proxy.ts` only requires a session (public: `/sign-in`, `/sign-up`); the server is the only enforcement. **4. Ownership is a test** — `UserOwnedMixin` and `tests/unit/models/test_owned_tables.py` (CI runs it in `module-boundaries.yml`).

- [ ] **Step 3: authentication.md, server.md, web-app.md — edits**

- `authentication.md`: Clerk owns identity and sessions (not organisations); sign-up is **public** (`sign_up_mode: public`) with pages at `/sign-in` and `/sign-up` in the app; the token table keeps `sub` and drops `o.id`/`o.rol` (a stale `o` claim is ignored); §4 the user row: created by JIT on first request or by `user.created`, synced by `user.updated`, erased by `user.deleted` — no membership events, no `org_id`; §6 table drops the organisation/role rows and the "Portal" column becomes "App".
- `server.md`: tree — account exports `CurrentUser`; drop the `supplier/` line, `CurrentRole`/`CurrentOrgId`/`require_role`, `SupplierID`; delete "The example domain" block; the `orders` sketch becomes a `transactions` sketch (`Transaction` carries `UserOwnedMixin`; `TransactionOwner` dependency → 404); R6 example uses `conversation` importing `account`; R7 → "A user-owned table carries `UserOwnedMixin`" and its test is `test_owned_tables.py`; §4 startup imports `account`, `conversation`; §5 AuthMiddleware sets `clerk_id` only; §8 events table: `USER_SYNCED` (JIT provisioning, `user.created`; no subscribers yet — the hook for first-sign-up seeding), `USER_ERASING` (`conversation`); delete `USER_OFFBOARDED`; §9 "Tenancy" → "Ownership" (UserOwnedMixin, CurrentUser, the test, 404); §11 rows follow.
- `web-app.md`: one app (`apps/web`) over six packages; delete "Two portals, not one app" and "§8 Adding a portal"; §2 tree has `(auth)/sign-in`, `(auth)/sign-up`, `(dashboard)/home`, no `unauthorized`; §3 who gets in = session only; §4 session table drops `role`; §6 one `.env.local`, `APP_NAME=web`; §7 test projects `packages` and `web`.

- [ ] **Step 4: setup docs**

- `clerk.md` — rewrite: intro (Clerk supplies authentication; the user is the tenant); make targets (`clerk-setup`, `clerk-apply-config`, `clerk-seed-users`, `clerk-check-config`, `clerk-pull-config`, `clerk-bootstrap-oauth`); **Reusing an existing instance** (set `CLERK_APP_ID`, pull and diff before applying, keep instance settings in `config.json`); §1 instance settings: organisations off, sign-up public, password sign-in, HIBP off at sign-in; §2 dev users Alice and Bob and the isolation check; §3 keys (one app); §4 `ALLOWED_ORIGINS` (`http://localhost:3000`, `http://localhost:8100`); §5 Swagger (reused OAuth client, redirect URI on 8100); §6 webhooks: three `user.*` events; §7 public sign-up (Account Portal sign-up on; app pages at `/sign-up`); §8 production instance; Symptom → cause table without org/role rows.
- `infrastructure.md`: `WEB_HOST_PORT` 3000 replaces the two portal rows; "starts the web app"; `web-app/apps/web/.env.local`; drop B2B wording at L162-163.
- `deploy-dokploy.md`: services `web`, `server`, `migrate`, `db`; `ALLOWED_ORIGINS` needs the web origin (`WEB_DOMAIN`); delete "Both portal images get the internal portal's build args"; "What deploy-check does not prove" names one web image.

- [ ] **Step 5: data-model, guide, index**

- `docs/data-model/README.md`: drop the supplier row and the supplier naming example (use `transactions.md` / `transaction.md`); the tenancy convention → "**Ownership is a test, not a convention.** A table owned by one user carries `UserOwnedMixin`, or sits in the allowlist of `test_owned_tables.py` with a reason."
- `docs/data-model/account.md`: status block revisions = `0c7838405158` only; schema sketch and indexes drop `org_id`/`ix_user_org_id`; D1 (nullable `org_id`) and D2 (`supplier.contact_id`) deleted, D3 renumbered; "No role column" → "No role: every user is equal".
- `docs/data-model/conversation.md` D2 → "`conversation` carries `UserOwnedMixin`; its `user_id` is the owner."
- `docs/guides/api-client-codegen.md`: L24-26 "shared by the app's pages"; L722-724 "another user's request"; leave the `@acme` suppliers illustration (it is a portable guide's example, not this repo).
- `docs/README.md`: rows for clerk.md ("Clerk setup — instance settings, keys, webhooks, dev users"), features/account.md ("Signing up, the profile, deleting an account"), server.md ("…events and ownership"), web-app.md ("one app over six packages"), authorization.md ("Ownership: the user is the tenant, 404 for another user's row"), authentication.md ("app, Clerk, token, API"), L76 "and the app's `README.md`"; delete the making-it-yours row.

- [ ] **Step 6: CLAUDE.md files and READMEs**

- `CLAUDE.md`: title `# Personal Finance — Monorepo Guide`; intro: "Personal Finance is a B2C app for tracking and understanding one person's money: a Next.js app (`web-app/apps/web`) backed by a FastAPI server. The user is the tenant — data is keyed by `user_id`; there are no organisations and no roles." Keep the product/data-model pointer paragraph. L39 ports **3000 and 8100**; L92-93 "the module and ownership tests"; L105 "what the app compiles against".
- `server/CLAUDE.md`: L65-67 "`account` cannot import `conversation`"; L121 logging example `logger.info("transactions_imported", count=count, source=source)`; L212-214 authentication: "`CurrentUser` is the only identity dependency; ownership of a row is the owning module's dependency, and a miss — including another user's row — is a 404"; L251 drop the role sentence; GDPR steps: drop the supplier step and "The role cache invalidated", renumber.
- `web-app/CLAUDE.md`: one Next.js 16 app; `pnpm dev` / `make dev-web` on 3000; test projects `packages`, `web`; delete role guidance (L104, L155-163) and the org/role pitfalls (L214, L215, L218); L219 "the root Makefile exports `apps/web/.env.local`".
- `README.md`: rewrite for Personal Finance (overview, structure with `apps/web`, env files, Clerk section pointing to `docs/setup/clerk.md` and naming `make clerk-setup` on an existing instance, services table with one web row, native development with `make dev-web`, testing, quality gates with "owned-table", documentation links) plus the Identity subsection from Step 1.
- `web-app/README.md`: one app, structure tree including `data-table`, setup (`cp apps/web/.env.example apps/web/.env.local`), `pnpm dev` on 3000, `pnpm --filter web add <package>`.
- `web-app/apps/web/README.md`: rewrite: title "Web"; routes `/sign-in`, `/sign-up`, `/home`; no roles, no `/unauthorized`; `make dev-web`; `@app/auth` exports `AuthProvider`, `useAppAuth`, `AppUser`.
- `server/README.md`: title `# Personal Finance — API Server`; "serving the web app. Handles authentication via Clerk; every row is scoped to its user."
- `server/docs/authentication.md`: delete "### 7. Supplier link" and the supplier cache row and any org-role cache material; `server/docs/gdpr-compliance-guide.md`: delete the supplier erasure step and org references; `server/docs/gdpr-erasure-findings.md`: add a one-line note at the top: "Findings predate the removal of the supplier module and organisations (2026-10-12); supplier and org_id items are moot." (it is an analysis record, not a living doc).

- [ ] **Step 7: Verify and commit**

```bash
git grep -n -i -E "supplier|organi[sz]ation|org_id|org_role|TenantMixin|require_role|CurrentRole|CurrentOrgId|project_manager|internal-portal|internal portal|two portals|3002|making-it-yours|template app" -- docs CLAUDE.md server/CLAUDE.md web-app/CLAUDE.md README.md server/README.md web-app/README.md web-app/apps/web/README.md server/docs
```

Every remaining hit must be intentional and listed in the commit message body (expected: `docs/guides/api-client-codegen.md`'s `@acme` example, the `gdpr-erasure-findings.md` note, and "there are no organisations" statements).

```bash
git add -A docs CLAUDE.md server/CLAUDE.md web-app/CLAUDE.md README.md server/README.md web-app/README.md web-app/apps/web/README.md server/docs
git commit -m "docs: architecture and setup docs for the single-tenant B2C base

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Product docs from the legacy `.planning/`

**Files:**
- Rewrite: `docs/product/prd-mvp.md`, `docs/product/README.md`, `docs/product/features/account.md`
- Create: `docs/product/features/{transactions,csv-import,categorisation,analytics,insights,chat,budgets}.md`
- Modify: `docs/README.md` (Product section rows), `docs/ROADMAP.md`, `docs/TODO.md`, `docs/BUGS.md`

**Sources (read-only):** `../pf-legacy/.planning/PROJECT.md`, `research/FEATURES.md`, `ROADMAP.md`, `MILESTONES.md`, `milestones/v1.0-REQUIREMENTS.md`; and the legacy code for what is actually built: `../pf-legacy/server/app/{api/v1,services,agents,analytics,tools}` and `../pf-legacy/web-app/src/app/(app)`.

- [ ] **Step 1: Follow the product conventions exactly**

From `docs/product/README.md` §Conventions: every doc opens with a status block (`**Status:** · **Owner:** Tiziano · **Last updated:** 2026-10-12 · **Scope:** · **Related:**`); status vocabulary `draft → agreed → shipped`, plus `superseded`; product docs hold intent and the field list, never schema; each feature doc links its data-model doc under **Data model** (write "pending — written with the backend module (sub-project 2)" for finance features); product decisions stay in the product doc; the README carries two index tables (PRDs; `### Features`) with columns Doc | Scope | Status | Last updated.

- [ ] **Step 2: prd-mvp.md**

Scope: a personal finance app for friends and family — each person uploads CSV bank exports and gets categorised transactions, analytics and AI insights; sign-up is public and each user sees only their own data. Sections: 1 Scope; 2 Account (link `features/account.md`); 3 Transactions; 4 CSV import; 5 Categorisation; 6 Analytics; 7 Insights; 8 Chat; 9 Budgets (not built — out of scope for the port); Decisions table with the port decisions from the spec's Decisions table that are product decisions (user is the tenant; public sign-up; no roles; budgets out of scope). Status `agreed` (the legacy v1.0 shipped it; the port rebuilds it).

- [ ] **Step 3: Feature docs**

One per area, status `shipped` for what legacy v1.0 shipped (to be rebuilt in sub-projects 2 and 3), `draft` for budgets. Each covers: who and why (one paragraph), what the user can do (bullets from `FEATURES.md` table stakes that legacy built, verified against the legacy routes/pages), the field list in product terms, rules and edge cases visible in the legacy code (e.g. CSV column mapping proposed by the LLM and confirmed by the user; mapping profiles remembered per bank; amounts are decimals, currency EUR by default; soft-deleted transactions), what is not built (from `FEATURES.md` anti-features: bank connection, multi-currency, households, splits), and open questions (from legacy `docs/TODO.md` items that are product questions). `budgets.md`: status `draft`, "Not built: the legacy app showed a Coming soon page and had no backend. Out of scope for the port."

`features/account.md` — rewrite: §1 Signing up and in (public sign-up at `/sign-up`; sign-in at `/sign-in`; the first request creates the account), §2 The profile (Clerk's profile modal), §3 Deleting an account (what is erased: name, email, avatar, conversations and chat history, long-term memory; finance data joins the cascade with each backend module), §4 Open questions. No organisations, no roles table, no supplier.

- [ ] **Step 4: Trackers**

- `docs/ROADMAP.md`: keep the preamble; `## Open` table rows: **Foundation** — single-tenant B2C base (in progress); **Backend modules** — transactions, CSV import, analytics, insights, finance agents (not started); **Frontend** — finance pages on the generated client (not started); **Cutover** — merge into `main`, retire legacy (not started); keep the WS7 row as is. Ordering notes: delete the two org/supplier bullets (L38, L40); keep L36 and L42.
- `docs/TODO.md`: delete "Tenancy — supplier adopts TenantMixin", "Authorization — the first organization-scoped route", "Authorization — strict role prefix on the server", "Clerk — supplier dev seed", "Clerk — offboarding policy", "Deploy — per-portal build args"; rewrite "Clerk — ticket-aware sign-up pages" as "Clerk — own sign-up page styling" only if still relevant, else delete; rewrite "Erasure — decide the target state" without supplier/C2; rewrite "Server — row-level security" for `user_id` / `UserOwnedMixin`; "Web — tests the suite does not have yet": "sign-up and sign-in through to a real screen". Add the still-applicable legacy items (from `../pf-legacy/docs/TODO.md`: N+1 in batch update/delete, services returning `None`, direct `ChatOpenAI` use) under a "Port — carry into backend modules" heading, each one line pointing at the legacy file.
- `docs/BUGS.md`: replace the intro's supplier example with a neutral one; in "connects as a superuser" reword tenancy to "other users' rows" / "the user id from the JWT"; portal wording → "the app" in the three web-app entries; the favicon entry is resolved by Task 7 (only the existing icon is declared) — delete it.
- `docs/README.md`: Product section rows for the new feature docs.

- [ ] **Step 5: Verify and commit**

```bash
for f in docs/product/prd-mvp.md docs/product/features/*.md; do head -12 "$f" | grep -q '\*\*Status:\*\*' || echo "missing status block: $f"; done
git grep -n -i -E "supplier|organi[sz]ation|role" -- docs/product docs/ROADMAP.md docs/TODO.md docs/BUGS.md
```

Expected: no "missing status block" lines; grep hits only "no roles"/"no organisations" statements.

```bash
git add -A docs
git commit -m "docs(product): Personal Finance PRD and feature docs from the legacy planning

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Project skills

**Files:**
- Delete: `.claude/skills/clerk-orgs/` and its entry in `skills-lock.json`
- Modify: `.claude/skills/{server-patterns,server-testing,web-app-patterns,web-app-testing,run-stack,worktrees,deploy-check}/**`
- Source to diff: `../pf-legacy/server/.claude/skills/fastapi-service-patterns/`

- [ ] **Step 1: Remove clerk-orgs**

```bash
git rm -r -q .claude/skills/clerk-orgs
jq 'del(.skills["clerk-orgs"])' skills-lock.json > skills-lock.json.tmp && mv skills-lock.json.tmp skills-lock.json
```

- [ ] **Step 2: server-patterns**

- `SKILL.md`: description "add a tenant-owned table" → "add a user-owned table"; "events and tenancy" → "events and ownership"; quick rule: "A user-owned table carries `UserOwnedMixin` (`user_id`, FK `user.id`) or a row in `test_owned_tables.py`'s ALLOWLIST (R7)"; events line: "`account` publishes `USER_SYNCED` and `USER_ERASING`"; drop "(`supplier`)".
- `references/api-routes.md`: L22 drop "`supplier` today"; **§Ownership**: the dependency raises the module's `NotFoundError` subclass for a missing, deleted or another user's row — show the new `get_user_conversation` body from Task 3; the `OrderOwner` example → `TransactionOwner` checking `transaction.user_id != user.id` → 404.
- `references/database.md`: "Tenant-owned tables" → "User-owned tables" (`UserOwnedMixin`, every query filters `user_id`); relationship-loading examples filter `Transaction.user_id == user_id`.
- `references/events.md`: drop the supplier examples (L13, L62-63) — use "a module that owns user data subscribes to `USER_ERASING`"; L82-83 "`organization_membership.created` webhook" → "`user.created` webhook".
- `references/exceptions.md`: delete `SupplierNotLinkedError` and `ConversationAccessDeniedError`; fix the tree glyphs.
- `references/new-module.md`: "Is the table user-owned? → `UserOwnedMixin`, else an ALLOWLIST row in `test_owned_tables.py`"; drop "(supplier has none)"; verify command names `test_owned_tables.py`.
- `references/webhooks.md` L127-130: only `user.*` handlers; `user.created` publishes `USER_SYNCED`.
- `references/client-wrappers.md` L8: `(account/, conversation/)`.
- **Legacy diff:** read `../pf-legacy/server/.claude/skills/fastapi-service-patterns/` (SKILL.md and refs). Add to the template skill only rules it lacks and that hold here; the known candidates: batch endpoints declare static routes before `/{id}` (api-routes); bulk operations validate that every id was found before mutating (database). Do **not** port rules the template contradicts (ints as ids, `user_id: str`, soft-delete-only for personal data, rate limit on every route).

- [ ] **Step 3: server-testing**

Description: drop role guard / org-scoped query / "expected 401, got 403" / test_tenant_tables; add "an ownership 404" and test_owned_tables. Delete §2 ("authenticated_client has a user and no role"); §3 → "No token is 401" (no guards exist); §4 example error code `CONVERSATION_NOT_FOUND`; Mocking: drop `supplier_cache`; "Tenancy" → "Ownership: create a second `User`, give it a row, assert the caller gets 404 with the module's not-found code"; gate-tests table row → `test_owned_tables.py`.

- [ ] **Step 4: web-app-patterns and web-app-testing**

- `web-app-patterns/SKILL.md`: one Next.js 16 app over six packages, `apps/web/`; drop "showing UI by role", "show this only to project managers", the "Adding a portal" row, "a role gate".
- `references/auth.md` → "Auth": what is already checked (proxy requires a session; sign-in and sign-up are public); reading the user (`useAppAuth()`: `user`, `isLoaded`, `getToken`, `signOut`); signing out; delete "Gating on role" and "Adding a role".
- `references/components.md`, `pages.md`, `server-side-fetch.md`: `apps/web`, `(dashboard)/`, one app; the suppliers page / sidebar examples → `TransactionsPage`, `{ title: "Transactions", url: "/transactions", icon: ArrowLeftRight }`, `/transactions/123`; drop `ROLE_LABELS`; verify with `make dev-web`.
- `examples/*`: first-line path comments `apps/internal-portal/...` → `apps/web/...`.
- `web-app-testing/SKILL.md`: project table `packages`, `web`; drop the `getUserRole` example; `apps/web/.env.local`; "The root React pin must match the app's"; "A second app".

- [ ] **Step 5: run-stack, worktrees, deploy-check**

- `run-stack/SKILL.md`: first-run copies `web-app/apps/web/.env.example`; "web app port"; "API server and web app"; "(web, server, db)".
- `worktrees/SKILL.md`: slot table columns `Web | API | DB`; defaults `3000 / 8100 / 5434`; "both `NEXT_PUBLIC_API_URL`s" → "the web app's `NEXT_PUBLIC_API_URL`".
- `deploy-check/SKILL.md`: one web image with its `APP_NAME`; `ALLOWED_ORIGINS` lists the web origin.

- [ ] **Step 6: Verify and commit**

```bash
git grep -n -i -E "supplier|organi[sz]ation|org_id|TenantMixin|require_role|role guard|project manager|internal-portal|two portals|3002|AccessDenied" -- .claude/skills ':!.claude/skills/clerk*'
```

Expected: nothing.

```bash
git add -A .claude skills-lock.json
git commit -m "chore(skills): project skills for the single-tenant B2C base

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Definition of done, then retire the spec

**Files:**
- Delete: `.superpowers/specs/2026-10-12-foundation-design.md`, `.superpowers/plans/2026-10-12-foundation.md`
- Modify: `docs/ROADMAP.md` (Foundation → done), any doc that lacks a lasting fact from the spec

- [ ] **Step 1: Every automated check**

```bash
make -C server test
make check
make test-web
cd web-app && pnpm type-check && pnpm --filter web build && cd ..
make check-contract
bash scripts/verify-infra.sh
make deploy-check
```

Expected: all pass. Record the output summary lines.

- [ ] **Step 2: [USER] The stack, in a browser**

```bash
make docker-run
make docker-migrate-status        # head = 0c7838405158
```

With the user at the browser:
1. Signed out, open `http://localhost:3000/sign-up` — the sign-up form shows (no bounce to `/sign-in`).
2. Sign up a brand-new address → lands on `/home`; the settings dialog's server-status indicator reads healthy.
3. Sign out; sign in as `dev-alice@example.com`, then in a private window as `dev-bob@example.com`. For each, open `http://localhost:8100/docs`, authorize, and call `GET /api/v1/auth/me` — each returns their own row (different `id`, matching `email`).
4. Open `http://localhost:3000/unauthorized` signed in — a 404 page, not an access-denied page.

- [ ] **Step 3: Leftover sweep**

```bash
git grep -n -i -E "supplier|organi[sz]ation|org_id|project_manager"
```

Expected hits only in: `.claude/skills/clerk*` (vendored), `docs/guides/api-client-codegen.md` (`@acme` example), `server/docs/gdpr-erasure-findings.md` (dated note), `scripts/clerk/config.json` (`organization_settings`), statements that there are no organisations, and the two `.superpowers/` files about to be deleted. Anything else is a leftover — fix it in the commit that owns it.

- [ ] **Step 4: Move the spec's lasting facts into docs, then delete it**

Check each against `docs/`, adding only what is missing:
- the port's four sub-projects and Foundation's status → `docs/ROADMAP.md` (Foundation: done);
- "the user is the tenant; 404 for another user's row" → `docs/architecture/authorization.md`;
- "reusing an existing Clerk instance: set `CLERK_APP_ID`, pull and diff before applying" → `docs/setup/clerk.md`;
- "the legacy app lives at tag `legacy-v0`; `template` is a git remote for merging template updates" → `README.md` (one short "History" paragraph).

```bash
git rm -q .superpowers/specs/2026-10-12-foundation-design.md .superpowers/plans/2026-10-12-foundation.md
git add -A docs README.md
git commit -m "docs: Foundation complete — lasting facts moved into docs

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 5: Report**

Summarise to the user: commits on `port/template` (`git log --oneline template/main..HEAD`), the check results from Step 1, the browser results from Step 2, and the intentional leftovers from Step 3. Do not push or open a PR unless asked.
