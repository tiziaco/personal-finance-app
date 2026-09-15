# B2C Hard Fork Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a reusable B2C template at `/Users/tizianoiacovelli/projects/fullstack-b2c-nextjs-fastapi-template` by forking the B2B template, stripping Clerk Organizations, the supplier domain and the second portal, and substituting a `publicMetadata`-sourced platform role.

**Architecture:** Strip-in-place. Copy the source repo's *tracked* files into the empty target, then remove B2B pieces in dependency order — deletions first, the org→role substitution next, the rename last — running the template's existing verification harness as the gate after each step. Work proceeds as ordinary commits for bisectability, then collapses to a single initial commit in the final task.

**Tech Stack:** FastAPI / SQLModel / PostgreSQL 16 (Python 3.13, uv), Next.js 16 / React 19 / TypeScript (pnpm workspaces), Clerk, Alembic, Docker Compose, Traefik on Dokploy.

**Spec:** `docs/superpowers/specs/2026-09-15-b2c-hard-fork-design.md` (in the **source** repo; read it alongside this plan)

## Global Constraints

- **Source commit:** fork from `cfca621` unless a newer `main` is explicitly chosen.
- **Target repo:** `/Users/tizianoiacovelli/projects/fullstack-b2c-nextjs-fastapi-template`, currently empty, `origin` = `git@github-personal:tiziaco/fullstack-b2c-nextjs-fastapi-template.git`.
- **Every command below runs in the TARGET repo** unless a step says otherwise.
- **Role values are exactly `user` and `admin`.** No other value may appear in `Role` on either side.
- **`Role` is the platform role only.** Per-resource capability is never added to this enum.
- **No DB mirror of the role.** `get_current_role` reads the token and nothing else.
- **No example business domain.** `User` and `Conversation` are the only models.
- **The AI stack stays** (`agents/`, `services/llm`, `services/conversation`). WS7 is not fixed here.
- **`docker-compose.dev.yml` publishes no new ports**; `docker-compose.prod.yml` publishes none at all.
- **Contract rule:** any change to `server/pyproject.toml`'s `[tool.app.metadata]` or `[project].version` must be committed **together with** regenerated `server/openapi.json` and `web-app/packages/api-client/src/generated/`.
- **Naming token stays `@app` / `app-network`.** Inherited deliberately; no rename.

---

## Task 1: Green baseline and tree copy

Establishes that every gate passes *before* anything is stripped, then seeds the target from tracked files only.

**Files:**
- Create: the entire target working tree
- Modify: none in the source repo

**Interfaces:**
- Produces: a target repo whose tree is byte-identical to source `HEAD`, on branch `main`, with one commit.

- [ ] **Step 1: Verify the source tree is clean and on the fork commit**

Run **in the source repo**:

```bash
cd /Users/tizianoiacovelli/projects/fullstack-multitenant-next-fastapi-tmp
git status --porcelain
git rev-parse --short HEAD
```

Expected: no output from `status`; `HEAD` is the commit you intend to fork from. Record it — it goes in the final commit message.

- [ ] **Step 2: Run the full gate set on the unmodified source**

Run **in the source repo**:

```bash
make check
make check-contract
bash scripts/verify-infra.sh
cd server && APP_ENV=test uv run pytest tests/ -q ; cd ..
```

Expected: `make check` silent (ruff + prettier + eslint clean), `check-contract` reports no drift, `verify-infra.sh` ends `SUMMARY: 19 passed, 0 failed`, pytest green.

**If any gate is already red, stop and fix it in the source repo first.** A gate that was red at baseline cannot tell you whether the fork broke something.

- [ ] **Step 3: Copy tracked files into the target**

`git archive` is used deliberately: it copies exactly what is committed, so no `.env.*`, `node_modules/`, `__pycache__/`, `.next/` or `*.tsbuildinfo` can leak into the template.

```bash
cd /Users/tizianoiacovelli/projects/fullstack-multitenant-next-fastapi-tmp
git archive HEAD | tar -x -C /Users/tizianoiacovelli/projects/fullstack-b2c-nextjs-fastapi-template
cd /Users/tizianoiacovelli/projects/fullstack-b2c-nextjs-fastapi-template
ls -la
```

Expected: the full tree, no `.env` files, no `node_modules`.

- [ ] **Step 4: Verify nothing untracked leaked**

```bash
cd /Users/tizianoiacovelli/projects/fullstack-b2c-nextjs-fastapi-template
find . -name '.env*' -not -name '.env.example' -not -path './.git/*'
find . -name node_modules -maxdepth 4 -not -path './.git/*'
find . -name '*.tsbuildinfo' -not -path './.git/*'
```

Expected: all three produce no output.

- [ ] **Step 5: Configure the new Clerk instance (start now — Task 4 blocks on it)**

The spec requires this to run alongside from the start: Task 4's substitution cannot be
verified without it, and dashboard changes propagate on the next token refresh, so doing it
late serialises the work for no reason.

In the Clerk dashboard, on a **new** instance (do not reuse the B2B one):

1. Leave **Organizations disabled**.
2. Create two test users. Set `publicMetadata` on each:
   - user A: `{"role": "user"}`
   - user B: `{"role": "admin"}`
3. Under **Sessions → Customize session token**, add the claim:

```json
{
  "role": "{{user.public_metadata.role}}"
}
```

4. Record the publishable key, secret key and the instance's issuer URL — they go into
   `web-app/apps/web/.env.local` and `server/.env.development` before Task 10's live gate.

Verify the claim actually lands before relying on it: sign in to the source repo's portal
against this instance if convenient, or defer the check to Task 10 Step 4, where a missing
claim presents as a 403 for *both* users.

- [ ] **Step 6: Commit the unmodified baseline**

```bash
cd /Users/tizianoiacovelli/projects/fullstack-b2c-nextjs-fastapi-template
git add -A
git commit -m "chore: baseline copy of the B2B template at cfca621

Working commit. Collapsed into a single initial commit in the final task."
git log --oneline
```

Expected: one commit on `main`.

---

## Task 2: Strip the supplier domain (server)

The largest and most entangled removal. Pure deletion — no behaviour is substituted here.

**Files:**
- Delete: `server/app/models/supplier.py`, `server/app/services/user/supplier_repository.py`, `server/app/integrations/clerk/webhooks/handlers/membership.py`
- Delete: `server/tests/integration/services/test_supplier_repository.py`, `server/tests/unit/services/test_supplier_linking.py`, `server/tests/unit/integrations/clerk/test_membership_handlers.py`
- Modify: `server/app/services/user/__init__.py`, `server/app/services/user/service.py`, `server/app/services/user/exceptions.py`, `server/app/services/user/cache.py`, `server/app/api/dependencies/authentication.py`, `server/app/api/dependencies/authorization.py`, `server/app/api/v1/auth.py`, `server/app/integrations/clerk/webhooks/dispatcher.py`, `server/app/integrations/clerk/webhooks/handlers/user.py`, `server/alembic/env.py`
- Modify (tests): `server/tests/unit/services/test_user_cache.py`, `server/tests/integration/services/test_user_service.py`, `server/tests/integration/api/test_auth_delete.py`, `server/tests/integration/api/test_webhooks.py`, `server/tests/unit/services/test_user_erasure.py`, `server/tests/unit/integrations/clerk/test_user_handlers.py`, `server/tests/unit/api/test_auth_dependencies.py`, `server/tests/README.md`

**Interfaces:**
- Produces: `UserService` with exactly four public methods — `resolve_user(clerk_id, org_id, session)`, `erase_user(user, session)`, `exists_in_clerk(clerk_id)`, `delete_user_from_clerk(clerk_id)`. (`resolve_user` still takes `org_id` at this point; Task 4 removes it.)
- Produces: `UserCache` with only the `org_role` cache remaining (Task 4 deletes the module entirely).

- [ ] **Step 1: Delete the supplier-only modules and their tests**

```bash
cd /Users/tizianoiacovelli/projects/fullstack-b2c-nextjs-fastapi-template
git rm server/app/models/supplier.py \
       server/app/services/user/supplier_repository.py \
       server/app/integrations/clerk/webhooks/handlers/membership.py \
       server/tests/integration/services/test_supplier_repository.py \
       server/tests/unit/services/test_supplier_linking.py \
       server/tests/unit/integrations/clerk/test_membership_handlers.py
```

- [ ] **Step 2: Run the suite to see exactly what breaks**

```bash
cd server && APP_ENV=test uv run pytest tests/ -q ; cd ..
```

Expected: FAIL — a wall of `ImportError` / `ModuleNotFoundError` for `app.models.supplier`, `supplier_repository`, and `handle_membership_*`. **Read the failure list; it is the authoritative to-do for the rest of this task.**

- [ ] **Step 3: Remove supplier exports from the user service package**

`server/app/services/user/__init__.py` — replace the whole file with:

```python
"""User service exports."""

from app.services.user.cache import (
    UserCache,
    user_cache,
)
from app.services.user.repository import (
    UserRepository,
    user_repository,
)
from app.services.user.service import (
    UserService,
    user_service,
)

__all__ = [
    "UserCache",
    "UserRepository",
    "UserService",
    "user_cache",
    "user_repository",
    "user_service",
]
```

- [ ] **Step 4: Remove `SupplierNotLinkedError`**

In `server/app/services/user/exceptions.py`, delete the `SupplierNotLinkedError` class entirely, and drop `AuthorizationError` from the import block at the top if nothing else in the file uses it. Verify:

```bash
grep -n "AuthorizationError" server/app/services/user/exceptions.py
```

Expected: no output. If there is output, keep the import.

- [ ] **Step 5: Remove the three supplier methods from `UserService`**

In `server/app/services/user/service.py`, delete these methods in full:
- `link_supplier_from_metadata`
- `get_supplier_id_for_user`
- `unlink_supplier_contact`

Then remove the call site inside `resolve_user` — this line at the end of the JIT branch:

```python
        await self.link_supplier_from_metadata(user, merge_clerk_metadata(clerk_user), session)
```

Leave `return user` as the final statement. Remove any import (`merge_clerk_metadata`, `supplier_repository`, `Supplier`) that is now unused.

Also update `erase_user`: delete the step that unlinks the supplier contact. Keep every other step.

- [ ] **Step 6: Remove the supplier cache**

In `server/app/services/user/cache.py`:
- delete `get_supplier_id` and `set_supplier_id`
- delete the `supplier_id` cache from `__init__` and from `clear()` / `reset()`
- in `invalidate_user`, drop the supplier-cache branch, keeping the `org_role` invalidation
- update the module docstring: it currently describes "two independent caches"; it now describes one

The `_Miss` sentinel stays — `get_org_role` returns it.

- [ ] **Step 7: Remove supplier-scoped identity from the auth dependencies**

In `server/app/api/dependencies/authentication.py`, delete the entire section under the `Supplier-scoped identity` comment banner: the `get_supplier_id` function and the `SupplierID` type alias. Remove the now-unused `SupplierNotLinkedError` import.

In `server/app/api/dependencies/authorization.py`, delete the `SupplierRole` guard line. Leave the other three guards for now — Task 4 replaces all of them.

- [ ] **Step 8: Clean supplier references out of docstrings and the dispatcher**

In `server/app/api/v1/auth.py`, in the `delete_me` docstring, remove step 5 (`Unlink any supplier this user managed`) and renumber the remaining steps; change step 7 to read `Invalidate the in-memory user cache (org role)`.

In `server/app/integrations/clerk/webhooks/dispatcher.py`, delete the entire `for _prefix in ("organizationMembership", "organization_membership"):` loop, its preceding comment block, and the `handle_membership_*` imports. The three `user.*` registrations stay.

In `server/app/integrations/clerk/webhooks/handlers/user.py`, `server/alembic/env.py` and `server/tests/README.md`, remove the remaining textual/import references to supplier. Find them with:

```bash
grep -rn "upplier" server/app server/alembic server/tests/README.md
```

- [ ] **Step 9: Strip supplier cases from the remaining tests**

Work through the failures from Step 2 in these files, deleting supplier-specific test functions, fixtures, imports and assertions:

`server/tests/unit/services/test_user_cache.py`, `server/tests/integration/services/test_user_service.py`, `server/tests/integration/api/test_auth_delete.py`, `server/tests/integration/api/test_webhooks.py`, `server/tests/unit/services/test_user_erasure.py`, `server/tests/unit/integrations/clerk/test_user_handlers.py`, `server/tests/unit/api/test_auth_dependencies.py`.

Delete tests that exist only to exercise supplier behaviour. For tests that merely *mention* a supplier (e.g. a fixture passing `supplier_id=`), keep the test and remove the supplier argument.

- [ ] **Step 10: Run the suite to green**

```bash
cd server && APP_ENV=test uv run pytest tests/ -q ; cd ..
```

Expected: PASS, zero errors.

- [ ] **Step 11: Confirm the domain is gone**

```bash
grep -rni "upplier" server/app server/tests server/alembic --exclude-dir=__pycache__
```

Expected: no output. (`server/alembic/versions/*_add_supplier_table.py` still exists and still matches — that is correct; Task 7 deletes it. Exclude `server/alembic/versions` from this grep if it is noisy, but do not delete the migration yet.)

- [ ] **Step 12: Commit**

```bash
git add -A
git commit -m "refactor: strip the supplier domain

Removes Supplier, supplier linking, the supplier repository, the org
membership webhook handlers, and the supplier cache. No substitution —
the B2C template ships no example business domain."
```

---

## Task 3: Strip the supplier portal

**Files:**
- Delete: `web-app/apps/supplier-portal/` (entire directory)
- Modify: `docker-compose.dev.yml:21-34`, `docker-compose.prod.yml:56-86`, `scripts/deploy-check.sh:48,71,85,92`

**Interfaces:**
- Produces: a single web app, `internal-portal` (renamed to `web` in Task 6). `docker-compose.prod.yml` declares exactly three routed services: `internal-portal`, `server`, and whatever else already carried Traefik labels.

- [ ] **Step 1: Delete the app**

```bash
git rm -r web-app/apps/supplier-portal
```

- [ ] **Step 2: Remove its dev compose service**

In `docker-compose.dev.yml`, delete the whole `supplier-portal:` service block (starts at the `supplier-portal:` key, ends at its `restart: always`). Nothing else in the dev file references it.

- [ ] **Step 3: Remove its prod compose service and Traefik labels**

In `docker-compose.prod.yml`, delete the whole `supplier-portal:` service block including all eight `traefik.*` labels and the `SUPPLIER_PORTAL_DOMAIN` references.

- [ ] **Step 4: Remove it from `deploy-check.sh`**

In `scripts/deploy-check.sh`:
- line ~48: `for app in internal-portal supplier-portal; do` → `for app in internal-portal; do`
- line ~71: delete the `export SUPPLIER_PORTAL_DOMAIN=...` line
- line ~85: `"${COMPOSE[@]}" build internal-portal supplier-portal server` → `"${COMPOSE[@]}" build internal-portal server`
- line ~92: `for app in internal-portal supplier-portal; do` → `for app in internal-portal; do`

- [ ] **Step 5: Verify both compose files still parse**

```bash
docker compose -f docker-compose.dev.yml config >/dev/null && echo "dev OK"
COMPOSE_PROJECT_NAME=b2c INTERNAL_PORTAL_DOMAIN=app.localhost API_DOMAIN=api.localhost \
  NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_x \
  docker compose -f docker-compose.prod.yml config >/dev/null && echo "prod OK"
```

Expected: `dev OK` and `prod OK`.

- [ ] **Step 6: Verify no dangling references**

```bash
grep -rni "supplier" --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=__pycache__ \
  --exclude-dir=.next . | grep -v "^./docs/" | grep -v "alembic/versions"
```

Expected: no output. Anything under `docs/` is handled in Task 9; the alembic file in Task 7.

- [ ] **Step 7: Lint the web workspace**

```bash
make check-web
```

Expected: clean. If pnpm complains about a missing workspace member, confirm `web-app/pnpm-workspace.yaml` uses a glob (`apps/*`) rather than naming portals explicitly; fix if it names them.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "refactor: remove the supplier portal

Deletes the second Next.js app, its dev and prod compose services, its
Traefik labels and SUPPLIER_PORTAL_DOMAIN, and its deploy-check assertions."
```

---

## Task 4: Server org → role substitution

The only real design work in the fork. TDD applies here properly: the middleware and `get_current_role` tests are rewritten *first*, and they fail before the implementation lands.

**Files:**
- Modify: `server/app/api/middlewares/auth.py`, `server/app/api/dependencies/authentication.py`, `server/app/api/dependencies/authorization.py`, `server/app/models/enums.py`, `server/app/models/user.py`, `server/app/services/user/service.py`, `server/app/services/user/repository.py`, `server/app/api/v1/auth.py`, `server/app/api/v1/api.py`
- Delete: `server/app/services/user/cache.py`, `server/tests/unit/services/test_user_cache.py`
- Create: `server/app/api/v1/admin.py`, `server/tests/integration/api/test_admin.py`
- Modify (tests): `server/tests/unit/middleware/test_auth_middleware.py`, `server/tests/integration/dependencies/test_role_dependencies.py`, `server/tests/unit/api/test_auth_dependencies.py`

**Interfaces:**
- Produces: `request.state.role: str | None` set by `AuthMiddleware` from the `role` claim. `request.state.org_id` and `request.state.org_role` no longer exist.
- Produces: `Role` = `StrEnum` with members `USER = "user"` and `ADMIN = "admin"`.
- Produces: `get_current_role(request) -> Role`, raising `AuthorizationError` when the claim is absent or unrecognised.
- Produces: `AdminOnly` — a `Depends` object from `require_role(Role.ADMIN)`.
- Produces: `resolve_user(clerk_id: str, session: AsyncSession) -> User` — the `org_id` parameter is gone.
- Produces: `GET /api/v1/admin/ping` → `{"ok": true}`, guarded by `AdminOnly`.

> **Spec amendment, decided in planning.** The spec's live gate assumes an `AdminOnly` endpoint exists. None does — in the source repo no production route uses any role guard; they are exercised only by throwaway routes inside `test_role_dependencies.py`. Shipping `require_role` and `AdminOnly` as dead code in a *template* is the worse outcome, so this task adds one deliberately minimal guarded endpoint. It is auth machinery, not business domain.

- [ ] **Step 1: Rewrite the middleware tests for the `role` claim**

Replace the three tests under the `# --- NEW: org claims ---` banner in `server/tests/unit/middleware/test_auth_middleware.py` with the following, and change `_make_app`'s endpoint to report `role` instead of `org_id`/`org_role`:

```python
def _make_app():
    """Create a minimal Starlette app with AuthMiddleware for testing."""

    async def endpoint(request: Request):
        return JSONResponse(
            {
                "clerk_id": getattr(request.state, "clerk_id", None),
                "user_id": getattr(request.state, "user_id", None),
                "role": getattr(request.state, "role", None),
            }
        )

    app = Starlette(routes=[Route("/test", endpoint)])
    app.add_middleware(AuthMiddleware)
    return app
```

```python
    @pytest.mark.asyncio
    @patch("app.api.middlewares.auth.clerk_jwt_verifier")
    async def test_role_claim_extracted_from_token(self, mock_verifier, app):
        """The custom `role` claim is sourced from Clerk publicMetadata.role."""
        mock_verifier.verify_token.return_value = {"sub": "user_abc123", "role": "admin"}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/test", headers={"Authorization": "Bearer valid.token"})

        assert response.json()["role"] == "admin"

    @pytest.mark.asyncio
    @patch("app.api.middlewares.auth.clerk_jwt_verifier")
    async def test_role_claim_not_prefix_stripped(self, mock_verifier, app):
        """Unlike org roles, the claim carries no 'org:' prefix and is stored verbatim."""
        mock_verifier.verify_token.return_value = {"sub": "user_u1", "role": "user"}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/test", headers={"Authorization": "Bearer token"})

        assert response.json()["role"] == "user"

    @pytest.mark.asyncio
    @patch("app.api.middlewares.auth.clerk_jwt_verifier")
    async def test_missing_role_claim_is_none(self, mock_verifier, app):
        """A token with no role claim leaves request.state.role unset."""
        mock_verifier.verify_token.return_value = {"sub": "user_abc123"}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/test", headers={"Authorization": "Bearer valid.token"})

        assert response.json()["role"] is None
```

- [ ] **Step 2: Run the middleware tests to verify they fail**

```bash
cd server && APP_ENV=test uv run pytest tests/unit/middleware/test_auth_middleware.py -q ; cd ..
```

Expected: FAIL — `role` is `None` because the middleware still reads the `o` claim.

- [ ] **Step 3: Rewrite the middleware**

Replace the class body of `server/app/api/middlewares/auth.py` with:

```python
class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware for extracting and verifying Clerk JWT tokens.

    Stores the following in request.state after a valid token:
      - clerk_id : Clerk user ID (sub claim)
      - role     : platform role, from the custom `role` claim, or None

    The `role` claim is configured in the Clerk dashboard as a session token
    customization sourcing user.public_metadata.role. There is no organization
    context in this template.

    The middleware is permissive — it does not block requests with invalid/missing
    tokens. Route-level dependencies determine if authentication is required.

    Note: after user provisioning, request.state.user_id is set to the internal UUID.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Parse the Clerk token, if any, and stash the identity on request.state."""
        request.state.clerk_id = None
        request.state.user_id = None
        request.state.role = None

        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            try:
                token = auth_header.split(" ")[1]
                payload = clerk_jwt_verifier.verify_token(token)

                if payload:
                    request.state.clerk_id = payload.get("sub")
                    request.state.role = payload.get("role")

                    logger.debug(
                        "token_verified_in_middleware",
                        clerk_id=request.state.clerk_id,
                        role=request.state.role,
                        path=request.url.path,
                    )
                else:
                    logger.debug("token_verification_failed_in_middleware", path=request.url.path)

            except (IndexError, ValueError) as e:
                logger.debug("token_extraction_failed", error=str(e), path=request.url.path)
        elif request.url.path not in ("/health", "/metrics"):
            logger.debug("no_auth_header_present", path=request.url.path)

        return await call_next(request)
```

This also removes the dead `/public/*` bypass — there are no `/public/*` routes and `link_token` appears nowhere else in the codebase.

- [ ] **Step 4: Run the middleware tests to verify they pass**

```bash
cd server && APP_ENV=test uv run pytest tests/unit/middleware/test_auth_middleware.py -q ; cd ..
```

Expected: PASS.

- [ ] **Step 5: Rewrite the `Role` enum**

Replace `server/app/models/enums.py` in full:

```python
"""Domain enumerations for the application."""

from enum import StrEnum


class Role(StrEnum):
    """Platform roles.

    Sourced from Clerk `publicMetadata.role` and delivered as a custom `role`
    claim on the session token. AuthMiddleware reads the claim; get_current_role
    validates it against this enum.

    Platform roles only. A per-resource capability — group moderator, page
    admin, recruiter — is not a role: it is scoped to a resource, non-exclusive
    and revocable, and a single-valued claim expresses none of the three. Model
    those as rows and check them per resource.

    Migration note: when switching auth providers, only AuthMiddleware and
    get_current_role change. This enum and all consumers remain unchanged.
    """

    USER = "user"
    ADMIN = "admin"
```

- [ ] **Step 6: Rewrite the role tests for `user` / `admin`**

Replace `server/tests/integration/dependencies/test_role_dependencies.py` in full:

```python
"""Integration tests for role-based access control dependencies."""

import pytest
from fastapi import APIRouter

from app.api.dependencies.authentication import get_current_role
from app.api.dependencies.authorization import AdminOnly
from app.main import app
from app.models.enums import Role

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module", autouse=True)
def role_test_routes():
    """Mount a sentinel endpoint with a role guard for the duration of this module."""
    router = APIRouter(prefix="/_test/rbac")

    @router.get("/admin-only", dependencies=[AdminOnly])
    async def _admin():
        return {"ok": True}

    original_routes = list(app.router.routes)
    app.include_router(router)
    yield
    app.router.routes[:] = original_routes


def _set_role(role: Role) -> None:
    app.dependency_overrides[get_current_role] = lambda: role


class TestAdminOnly:
    async def test_admin_passes(self, authenticated_client):
        _set_role(Role.ADMIN)
        response = await authenticated_client.get("/_test/rbac/admin-only")
        assert response.status_code == 200

    async def test_user_blocked(self, authenticated_client):
        _set_role(Role.USER)
        response = await authenticated_client.get("/_test/rbac/admin-only")
        assert response.status_code == 403


class TestMissingRole:
    async def test_no_role_returns_403(self, client):
        # No get_current_role override — request.state.role is None,
        # so get_current_role raises AuthorizationError -> 403.
        response = await client.get("/_test/rbac/admin-only")
        assert response.status_code == 403
```

- [ ] **Step 7: Run those tests to verify they fail**

```bash
cd server && APP_ENV=test uv run pytest tests/integration/dependencies/test_role_dependencies.py -q ; cd ..
```

Expected: FAIL — `ImportError: cannot import name 'AdminOnly'`.

- [ ] **Step 8: Rewrite `get_current_role` and the guards**

In `server/app/api/dependencies/authentication.py`, replace `get_current_role` in full:

```python
async def get_current_role(
    request: Request,
    _token: str = Depends(oauth2_scheme),
) -> Role:
    """Extract the platform role from request.state.

    This is the backend portability seam. The role arrives as a custom `role`
    claim on the Clerk session token, sourced from publicMetadata.role. The
    token is the only source — there is deliberately no database mirror and no
    provider-API fallback, so a role change propagates on the next token
    refresh and nothing can go stale independently.

    Raises:
        AuthorizationError: If no role is present or the role is unrecognised.
    """
    raw = getattr(request.state, "role", None)

    if not raw:
        raise AuthorizationError("No role in token")

    try:
        return Role(raw)
    except ValueError:
        raise AuthorizationError(f"Unknown role: {raw}")
```

In the same file, change `get_current_user` to drop the org lookup — replace its body's first two lines:

```python
        user = await user_service.resolve_user(clerk_id, session)
```

(removing the `org_id = getattr(request.state, "org_id", None)` line above it).

In `server/app/api/dependencies/authorization.py`, replace everything below the `require_role` factory with:

```python
# ---------------------------------------------------------------------------
# Role guards — use in endpoint `dependencies=[...]` list
# ---------------------------------------------------------------------------

# Platform administrators only
AdminOnly = require_role(Role.ADMIN)
```

Update the factory's usage docstring example to `@router.get("/admin/ping", dependencies=[AdminOnly])`, and update the module docstring: the "does this supplier own this order?" example should read "does this user own this conversation?".

- [ ] **Step 9: Run those tests to verify they pass**

```bash
cd server && APP_ENV=test uv run pytest tests/integration/dependencies/test_role_dependencies.py -q ; cd ..
```

Expected: PASS.

- [ ] **Step 10: Write the failing test for the admin endpoint**

Create `server/tests/integration/api/test_admin.py`:

```python
"""Integration tests for the admin smoke endpoint."""

import pytest

from app.api.dependencies.authentication import get_current_role
from app.main import app
from app.models.enums import Role

pytestmark = pytest.mark.integration


class TestAdminPing:
    async def test_admin_gets_ok(self, authenticated_client):
        app.dependency_overrides[get_current_role] = lambda: Role.ADMIN
        response = await authenticated_client.get("/api/v1/admin/ping")
        assert response.status_code == 200
        assert response.json() == {"ok": True}

    async def test_user_is_forbidden(self, authenticated_client):
        app.dependency_overrides[get_current_role] = lambda: Role.USER
        response = await authenticated_client.get("/api/v1/admin/ping")
        assert response.status_code == 403
```

- [ ] **Step 11: Run it to verify it fails**

```bash
cd server && APP_ENV=test uv run pytest tests/integration/api/test_admin.py -q ; cd ..
```

Expected: FAIL with 404 — the route does not exist.

- [ ] **Step 12: Add the admin router**

Create `server/app/api/v1/admin.py`:

```python
"""Administrative endpoints.

Ships one endpoint deliberately: it is the worked example of `AdminOnly` and
the only production route that exercises the role seam end to end. Replace or
extend it with real administrative endpoints; do not delete the guard.
"""

from fastapi import APIRouter

from app.api.dependencies.authorization import AdminOnly

router = APIRouter()


@router.get(
    "/ping",
    operation_id="adminPing",
    summary="Admin-only smoke endpoint",
    description="Returns 200 for a caller whose role is `admin`, 403 otherwise. "
    "Exists to verify the role claim, the middleware and require_role() end to end.",
    dependencies=[AdminOnly],
)
async def admin_ping() -> dict[str, bool]:
    """Confirm the caller holds the admin platform role."""
    return {"ok": True}
```

In `server/app/api/v1/api.py`, add the import and the registration:

```python
from app.api.v1.admin import router as admin_router
```

```python
api_router.include_router(admin_router, prefix="/admin", tags=["admin"])
```

- [ ] **Step 13: Run it to verify it passes**

```bash
cd server && APP_ENV=test uv run pytest tests/integration/api/test_admin.py -q ; cd ..
```

Expected: PASS.

- [ ] **Step 14: Delete the cache module**

Both of `UserCache`'s caches are gone — `supplier_id` in Task 2, `org_role` with `resolve_org_role` here.

```bash
git rm server/app/services/user/cache.py server/tests/unit/services/test_user_cache.py
```

In `server/app/services/user/service.py`: delete `resolve_org_role`, every `user_cache.*` call, and the `user_cache` / `_MISS` imports.
In `server/app/services/user/__init__.py`: remove the `UserCache` / `user_cache` imports and their `__all__` entries.
In `server/app/api/v1/auth.py`: remove the cache-invalidation step from `delete_me` and its docstring line.

Then drop the dependency:

```bash
cd server && uv remove cachetools && cd ..
```

If `uv remove` reports `cachetools` is still required by another package, leave it in the lockfile and only remove the direct entry from `[project.dependencies]` in `server/pyproject.toml`.

- [ ] **Step 15: Remove org from the model, repository and service**

`server/app/models/user.py`: delete the `org_id` field, its docstring paragraph, and the `self.org_id = None` line in `anonymize_user`.

`server/app/services/user/repository.py`: delete `update_org_id` (line ~154) and remove the `org_id` parameter from `create_or_get` and from the `create` path it calls, along with the `org_id=org_id` kwargs and the `org_id=org_id` field in the `logger.info("user_created", ...)` call.

`server/app/services/user/service.py`: change `resolve_user`'s signature to `async def resolve_user(self, clerk_id: str, session: AsyncSession) -> User:`. Delete:
- the `if org_id and user.org_id != org_id:` sync branch
- the whole `if not org_id:` JIT block, **including `raise AuthorizationError("Organization membership required")`** — in a consumer app that rejects every new signup
- the `org_id=org_id` kwarg in the `create_or_get` call
- the now-unused `get_first_org_membership` import and `AuthorizationError` import if nothing else uses it

Update the docstring to drop the org sync paragraph and the `org_id` argument.

- [ ] **Step 16: Fix the remaining tests and run the whole suite**

```bash
cd server && APP_ENV=test uv run pytest tests/ -q ; cd ..
```

Work through failures in `server/tests/unit/api/test_auth_dependencies.py` and any integration test that sets `request.state.org_role` or passes `org_id=` to `resolve_user` / `create_or_get`. Replace `org_role` with `role` and delete `org_id` arguments. Repeat until green.

Expected, finally: PASS.

- [ ] **Step 17: Confirm the org seam is gone**

```bash
grep -rn "org_id\|org_role\|organization" server/app server/tests --exclude-dir=__pycache__
```

Expected: no output.

- [ ] **Step 18: Commit**

```bash
git add -A
git commit -m "feat: source the platform role from Clerk publicMetadata

AuthMiddleware reads a custom \`role\` claim instead of the org claim; the
token is the only source, so resolve_org_role, the user cache and cachetools
are gone. Roles are user/admin. Adds GET /api/v1/admin/ping as the worked
example of AdminOnly — without it require_role ships as dead code.

Also removes the dead /public/* auth bypass: no such routes exist and
link_token appears nowhere in the codebase."
```

---

## Task 5: Frontend org → role substitution

**Files:**
- Modify: `web-app/packages/auth/src/permissions.ts`, `web-app/packages/auth/src/provider.tsx`, `web-app/apps/internal-portal/src/proxy.ts`, `web-app/packages/ui/src/components/layout/user-panel.tsx`, `web-app/apps/internal-portal/src/components/layout/clerk-user-panel.tsx`

**Interfaces:**
- Produces: `Role` = `{ USER: "user", ADMIN: "admin" }`, `getUserRole(role: string | null | undefined): Role | null`, `isAdmin(role: Role | null): boolean`, `ROLE_LABELS: Record<Role, string>` — all exported from `@app/auth`.
- Produces: `useAppAuth()` returning `{ user, role, isLoaded, getToken }` with `role: Role | null`, unchanged in shape.

> **Note on the edge gate.** In the B2B template `proxy.ts` gated routes by role because there were two portals. With one app and no `/admin` routes there is nothing to gate — `proxy.ts` becomes `auth.protect()` only. The role still rides the session token because a fork adding admin routes or a second app needs it at the edge, and `useAppAuth()` exercises it client-side. Do not conclude from `proxy.ts` that the claim is unused.

- [ ] **Step 1: Confirm how the installed Clerk version exposes the claim**

```bash
cd web-app && pnpm ls @clerk/nextjs --depth 0
grep -rn "sessionClaims" node_modules/@clerk/nextjs/dist/types/index.d.ts \
  node_modules/@clerk/shared/dist/react/index.d.ts 2>/dev/null | head
cd ..
```

Expected: `useAuth()`'s return type includes `sessionClaims`. **If it does not**, use the fallback in Step 3's note. Record which one you used.

- [ ] **Step 2: Rewrite `permissions.ts`**

Replace `web-app/packages/auth/src/permissions.ts` in full:

```typescript
/**
 * Role definitions and utilities for RBAC.
 *
 * Portability seam: getUserRole() is the only function that knows how
 * the auth provider represents roles. When migrating providers, only
 * this function changes — all consumers remain unchanged.
 */

/**
 * Platform roles, sourced from Clerk publicMetadata.role.
 *
 * Platform roles only. A per-resource capability — group moderator, page
 * admin — is not a role: it is scoped, non-exclusive and revocable, and a
 * single-valued claim expresses none of the three. Model those as rows.
 */
export const Role = {
  USER: "user",
  ADMIN: "admin",
} as const

export type Role = (typeof Role)[keyof typeof Role]

/**
 * Convert a raw role claim to a Role value.
 *
 * Returns null when the claim is absent or unrecognised, so an unknown value
 * can never be treated as a valid role.
 *
 * @example
 * getUserRole("admin")   // → "admin"
 * getUserRole("hacker")  // → null
 * getUserRole(null)      // → null
 */
export function getUserRole(role: string | null | undefined): Role | null {
  if (!role) return null
  const values = Object.values(Role) as string[]
  if (!values.includes(role)) return null
  return role as Role
}

/** Returns true only for platform administrators. */
export function isAdmin(role: Role | null): boolean {
  return role === Role.ADMIN
}

/** Display labels — mapped in the frontend only. */
export const ROLE_LABELS: Record<Role, string> = {
  [Role.USER]: "User",
  [Role.ADMIN]: "Admin",
}
```

- [ ] **Step 3: Rewrite `provider.tsx`'s role derivation**

In `web-app/packages/auth/src/provider.tsx`, change the `AuthProvider` body:

```tsx
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { isLoaded, sessionClaims, getToken } = useAuth()
  const { user } = useUser()
  const role = getUserRole(sessionClaims?.role as string | undefined)

  return (
    <AuthContext.Provider value={{ user, role, isLoaded, getToken }}>
      {children}
    </AuthContext.Provider>
  )
}
```

**If Step 1 showed `useAuth()` has no `sessionClaims`**, use this instead — `publicMetadata` is readable client-side on `UserResource` and needs no custom claim:

```tsx
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { isLoaded, getToken } = useAuth()
  const { user } = useUser()
  const role = getUserRole(user?.publicMetadata?.role as string | undefined)

  return (
    <AuthContext.Provider value={{ user, role, isLoaded, getToken }}>
      {children}
    </AuthContext.Provider>
  )
}
```

Update the `role` field's doc comment in `AuthContextValue` from "The current user's org role, or null if no active org context." to "The current user's platform role, or null if absent or unrecognised."

- [ ] **Step 4: Simplify `proxy.ts`**

Replace `web-app/apps/internal-portal/src/proxy.ts`'s middleware body:

```typescript
import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server"

const isPublicRoute = createRouteMatcher(["/sign-in(.*)", "/sign-up(.*)"])

export default clerkMiddleware(async (auth, req) => {
  // Allow public routes (sign-in, sign-up) without auth
  if (isPublicRoute(req)) return

  // Every signed-in user may use the app. Role gating belongs on the routes
  // that need it: add a matcher here (e.g. /admin(.*)) reading
  // sessionClaims.role through getUserRole() when such routes exist.
  await auth.protect()
})
```

Keep the existing `export const config = { matcher: [...] }` block unchanged. Remove the now-unused `NextResponse` and `@app/auth` imports.

- [ ] **Step 5: Remove the organization UI**

In `web-app/packages/ui/src/components/layout/user-panel.tsx`: delete the `onOpenOrganizationProfile?: () => void` prop from the interface, its destructured parameter, and the menu item block rendering the "Organisation" entry. Simplify the two `{(onOpenProfile || onOpenOrganizationProfile) && (` conditions to `{onOpenProfile && (`.

In `web-app/apps/internal-portal/src/components/layout/clerk-user-panel.tsx`: remove `openOrganizationProfile` from the `useClerk()` destructure and delete the `onOpenOrganizationProfile={...}` prop passed to `UserPanel`.

- [ ] **Step 6: Type-check and lint**

```bash
cd web-app && pnpm -r exec tsc --noEmit ; cd ..
make check-web
```

Expected: both clean. Note that `packages/types` has no `tsconfig.json` (pre-existing), so it is skipped — that is not a regression.

- [ ] **Step 7: Confirm the org seam is gone from the frontend**

```bash
grep -rni "orgrole\|org_id\|organization" web-app/apps web-app/packages \
  --exclude-dir=node_modules --exclude-dir=.next
```

Expected: no output.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat(web): derive the platform role from the Clerk role claim

getUserRole stops stripping an org: prefix; isInternalRole/isSupplierRole
become isAdmin; labels move to English. proxy.ts drops role gating — with
one app and no admin routes there is nothing to gate — and the organization
profile entry leaves the user panel."
```

---

## Task 6: Rename `internal-portal` to `web`

Mechanical but wide. Done after all deletions so the file set is stable.

**Files:**
- Move: `web-app/apps/internal-portal/` → `web-app/apps/web/`
- Modify: `web-app/apps/web/package.json`, `docker-compose.dev.yml`, `docker-compose.prod.yml`, `Makefile:24`, `scripts/deploy-check.sh`, `web-app/apps/web/README.md`, and any `pnpm --filter` reference

**Interfaces:**
- Produces: workspace package named `web`; compose `APP_NAME: web`; env file at `web-app/apps/web/.env.local`; Traefik router/service labels keyed `${COMPOSE_PROJECT_NAME}-web`; domain variable `WEB_DOMAIN`.

- [ ] **Step 1: Move the directory**

```bash
git mv web-app/apps/internal-portal web-app/apps/web
```

- [ ] **Step 2: Find every remaining reference**

```bash
grep -rn "internal-portal\|internal_portal\|INTERNAL_PORTAL" . \
  --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=.next --exclude-dir=__pycache__
```

Expected: hits in `web-app/apps/web/package.json`, both compose files, `Makefile`, `scripts/deploy-check.sh`, and docs. Work through every one.

- [ ] **Step 3: Rename the workspace package**

In `web-app/apps/web/package.json`, set `"name": "web"`.

- [ ] **Step 4: Update the compose files**

`docker-compose.dev.yml`: service key `internal-portal:` → `web:`; `container_name: internal-portal` → `container_name: web`; `env_file` path → `./web-app/apps/web/.env.local`; `APP_NAME: internal-portal` → `APP_NAME: web`.

`docker-compose.prod.yml`: the same four, plus every Traefik label — replace `${COMPOSE_PROJECT_NAME}-internal-portal` with `${COMPOSE_PROJECT_NAME}-web`, `internal-portal-web`/`internal-portal-secure` router names with `web-web`/`web-secure`, and `INTERNAL_PORTAL_DOMAIN` with `WEB_DOMAIN` (keeping the `:?set to ...` required-variable form, updating its message).

> Router names must stay unique across services. `web-web` reads oddly but is correct: the first token is the service, the second the entrypoint. Rename to `web-http`/`web-https` only if you also change the `.entrypoints=` values to match, which you should not — Dokploy's entrypoints are named `web` and `websecure`.

- [ ] **Step 5: Update the Makefile include**

`Makefile:24`: `-include web-app/apps/internal-portal/.env.local` → `-include web-app/apps/web/.env.local`.

> This is the single-key build-arg trap from the spec. It is correct at one app. If a fork adds a second app on a different Clerk instance, both images will bake this app's key and `deploy-check` will not notice.

- [ ] **Step 6: Update `deploy-check.sh`**

Replace `internal-portal` with `web` at every occurrence (the two `for app in` loops, the `build` invocation), and `INTERNAL_PORTAL_DOMAIN` with `WEB_DOMAIN` in the export block.

- [ ] **Step 7: Verify the rename is complete**

```bash
grep -rn "internal-portal\|INTERNAL_PORTAL" . \
  --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=.next --exclude-dir=__pycache__ \
  | grep -v "^./docs/"
```

Expected: no output. Docs are handled in Task 9.

- [ ] **Step 8: Verify the stack builds and boots**

```bash
docker compose -f docker-compose.dev.yml config >/dev/null && echo "dev OK"
bash scripts/verify-infra.sh
```

Expected: `dev OK`; `verify-infra.sh` passes. **If `verify-infra.sh` asserts on portal names, update its expectations** — it is a checker of this repo's layout, not an external contract.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "refactor: rename internal-portal to web

One app, neutrally named. Touches the directory, the workspace package,
both compose files including the Traefik labels, the Makefile env include
and deploy-check. INTERNAL_PORTAL_DOMAIN becomes WEB_DOMAIN."
```

---

## Task 7: Collapse the Alembic migrations

Three revisions become one. Safe because the template has no production data — `docs/setup/making-it-yours.md` §4 endorses exactly this over a rename revision.

**Files:**
- Delete: `server/alembic/versions/20260411_1650_0c7838405158_initial_schema.py`, `server/alembic/versions/20260825_0838_9bcca25cfef3_add_supplier_table.py`, `server/alembic/versions/20260825_0900_b3f1c27a4e18_make_user_org_id_nullable.py`
- Create: one new initial revision under `server/alembic/versions/`

**Interfaces:**
- Produces: a single Alembic head with `down_revision = None`, producing `user` and `conversation` tables (plus any LangGraph checkpoint tables the current chain creates) and **no** `supplier` table and **no** `user.org_id` column.

- [ ] **Step 1: Delete the three revisions**

```bash
git rm server/alembic/versions/20260411_1650_0c7838405158_initial_schema.py \
       server/alembic/versions/20260825_0838_9bcca25cfef3_add_supplier_table.py \
       server/alembic/versions/20260825_0900_b3f1c27a4e18_make_user_org_id_nullable.py
```

- [ ] **Step 2: Start a database on an empty volume**

```bash
make clean
make docker-run-db ENV=development
```

Expected: a Postgres container, empty, with no `alembic_version` table.

- [ ] **Step 3: Autogenerate the new initial revision**

The target requires **both** `ENV` and `MSG` (`server/Makefile:224`); it errors out naming
the missing one if either is absent.

```bash
cd server && make migrate-create ENV=development MSG="initial schema" ; cd ..
```

It needs `server/.env.development` to exist. If you have not created it yet:

```bash
cp server/.env.example server/.env.development   # then fill in the values
```

- [ ] **Step 4: Read the generated file before trusting it**

Open the new file under `server/alembic/versions/`. Confirm:
- `down_revision: Union[str, Sequence[str], None] = None`
- it creates `user` **without** an `org_id` column
- it creates `conversation`
- it does **not** create `supplier`
- no `drop_*` operations (an autogenerate against an empty DB should only create)

Fix anything wrong by hand — autogenerate is a draft, not an authority.

- [ ] **Step 5: Apply it from empty and verify**

```bash
make docker-migrate
make docker-migrate-status
```

Expected: migration applies cleanly; status prints the new revision as current.

- [ ] **Step 6: Confirm the schema**

```bash
docker compose -f docker-compose.dev.yml exec -T db \
  psql -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-app}" -c '\d "user"'
```

Expected: no `org_id` column. If the `psql` credentials differ, read them from `server/.env.development`.

- [ ] **Step 7: Run the full suite against the new schema**

```bash
cd server && APP_ENV=test uv run pytest tests/ -q ; cd ..
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "refactor(db): collapse three migrations into one initial schema

No production data exists, so a clean initial revision beats a rename
revision plus a drop-column. Produces user and conversation, with no
supplier table and no user.org_id."
```

---

## Task 8: Service identity and contract regeneration

**Files:**
- Modify: `server/pyproject.toml`, root `.env.example`, `server/.env.example`
- Regenerate: `server/openapi.json`, `web-app/packages/api-client/src/generated/`

**Interfaces:**
- Produces: an OpenAPI document whose `info.title` names the B2C template and which includes `GET /api/v1/admin/ping` with `operationId: adminPing`.

- [ ] **Step 1: Set the service identity**

In `server/pyproject.toml`, under `[tool.app.metadata]`:

```toml
title = "B2C Template - Server"
description = "A production-ready FastAPI service with LangGraph and Clerk authentication, for consumer applications."
api_v1_str = "/api/v1"
```

Under `[project]`, set `version = "0.1.0"` and update `description` to match.

- [ ] **Step 2: Update the env examples**

Root `.env.example`: set `COMPOSE_PROJECT_NAME` to the new project name; replace `INTERNAL_PORTAL_DOMAIN` and `SUPPLIER_PORTAL_DOMAIN` with a single `WEB_DOMAIN`.

`server/.env.example`: update `PROJECT_NAME` (this tags Docker images only — it is not the API title).

- [ ] **Step 3: Regenerate the contract**

```bash
make gen-contract
```

Expected: `server/openapi.json` and the generated client tree are rewritten.

- [ ] **Step 4: Verify the contract reflects the new surface**

```bash
grep -n '"title"' server/openapi.json | head -3
grep -c "adminPing" server/openapi.json
grep -rn "supplier\|Supplier" server/openapi.json web-app/packages/api-client/src/generated/ | head
```

Expected: the new title; `adminPing` present at least once; **no** supplier hits.

- [ ] **Step 5: Confirm there is no drift**

```bash
make check-contract
```

Expected: exits 0.

- [ ] **Step 6: Commit the source change and the artifacts together**

The contract rule: these must be one commit.

```bash
git add server/pyproject.toml server/openapi.json web-app/packages/api-client/src/generated .env.example server/.env.example
git commit -m "chore: set the B2C service identity and regenerate the contract

pyproject metadata lands verbatim in openapi.json and in every generated
client header, so the artifacts are regenerated in the same commit."
```

---

## Task 9: Documentation

**Files:**
- Create: `docs/setup/deploy-dokploy.md`
- Delete: `docs/superpowers/` (entire tree), `docs/RBAC/roles_definition.md`
- Modify: `CLAUDE.md`, `server/CLAUDE.md`, `web-app/CLAUDE.md`, `docs/README.md`, `docs/setup/making-it-yours.md`, `docs/setup/clerk.md`, `docs/setup/infrastructure.md`, `docs/setup/clerk-webhooks.md`, `web-app/apps/web/README.md`

- [ ] **Step 1: Extract the Dokploy knowledge before deleting its home**

Create `docs/setup/deploy-dokploy.md` from the **"How Dokploy actually configures Traefik"** and **"A constraint to carry to the first deploy"** sections of the source repo's `docs/superpowers/specs/2026-09-03-ws2-traefik-dokploy-deploy-design.md`. Read it from the source checkout:

```bash
sed -n '73,127p' /Users/tizianoiacovelli/projects/fullstack-multitenant-next-fastapi-tmp/docs/superpowers/specs/2026-09-03-ws2-traefik-dokploy-deploy-design.md
```

The new document must carry, at minimum:
- entrypoints `web` (80) and `websecure` (443); cert resolver named `letsencrypt`, HTTP challenge, applied only to `websecure` routers
- the `dokploy-network` requirement: a Compose deployment lands only in its own project network unless the file joins `dokploy-network` explicitly — Dokploy issue #3435, and the most common cause of a deploy that builds cleanly then 404s
- that Dokploy's Domains tab and hand-written labels are **both** labels, so mixing them yields two routers matching one Host (issue #3222)
- that `ALLOWED_ORIGINS` (`server/app/core/config.py:217` — **verify the line number**, `CLAUDE.md` cites a stale `:208`) gates both CORS and the Clerk `azp` check in `server/app/utils/auth.py:72`, so a missing origin looks like broken auth
- that `make deploy-check` does **not** exercise the Traefik labels

Rewrite for a reader deploying *this* template. Drop the WS2 decision history, acceptance criteria and the superseded tunnelled-staging appendix.

- [ ] **Step 2: Drop the planning history**

```bash
git rm -r docs/superpowers
git rm docs/RBAC/roles_definition.md
rmdir docs/RBAC 2>/dev/null || true
```

- [ ] **Step 3: Rewrite the root `CLAUDE.md`**

The current file describes a multi-tenant B2B platform with two portals and supplier document compliance. Rewrite the header, **Repo Structure**, **Service URLs** and **Deploying** sections for: one portal (`web`, port 3000), no organizations, no example domain, role from `publicMetadata`. Remove the supplier-portal row from the URL table and the paragraph about both portal images baking the internal portal's key — replace it with the single-app version of the same warning. Fix the `config.py:208` reference to `:217`.

- [ ] **Step 4: Rewrite the remaining setup docs**

- `docs/setup/making-it-yours.md` — §2's per-portal table becomes one app; §4 ("The example domain") is replaced by a short section explaining that the template ships no domain and pointing at `admin.py` as the role-guard example; the role-rename note becomes "change the enum **and** `publicMetadata.role` on existing users".
- `docs/setup/clerk.md` — replace organization setup with: Organizations off, `publicMetadata.role` on users, and the session-token customization `{"role": "{{user.public_metadata.role}}"}`.
- `docs/setup/infrastructure.md` — one portal; link to the new `deploy-dokploy.md`.
- `docs/setup/clerk-webhooks.md` — remove organization membership events; keep `user.created` / `user.updated` / `user.deleted`.
- `docs/README.md` — update the index; remove links into `docs/superpowers/`.
- `web-app/apps/web/README.md`, `server/CLAUDE.md`, `web-app/CLAUDE.md` — remove supplier and two-portal references.

- [ ] **Step 5: Verify no dangling references**

```bash
grep -rn "superpowers\|supplier\|internal-portal\|organization" \
  --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=.next --exclude-dir=__pycache__ . \
  | grep -vi "organizationmembership.*removed"
```

Expected: no output.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "docs: rewrite for the B2C template

Drops docs/superpowers (B2B planning history) after extracting its Dokploy
and Traefik facts into docs/setup/deploy-dokploy.md, which is where a reader
looking to deploy will actually find them."
```

---

## Task 10: Final verification and the initial commit

**Files:** none modified — this task verifies, then rewrites history.

- [ ] **Step 1: Run every gate**

```bash
make check
make check-contract
bash scripts/verify-infra.sh
cd server && APP_ENV=test uv run pytest tests/ -q ; cd ..
```

Expected: all green, matching the Task 1 baseline.

- [ ] **Step 2: Boot the core stack**

```bash
make clean
make docker-run-core
docker compose -f docker-compose.dev.yml ps
curl -sS http://localhost:8100/health
```

Expected: `web`, `server` and `db` running, `server` reporting `healthy`; `/health` returns 200.

- [ ] **Step 3: Run the deploy check**

```bash
make deploy-check
```

Expected: passes. It needs `server/.env.staging` (gitignored — create it from `server/.env.example`) and, once per machine, `docker network create dokploy-network`.

Remember what it does **not** prove: the Traefik labels are never exercised, and this fork changed them. Review them against `docs/setup/deploy-dokploy.md` by hand.

- [ ] **Step 4: The live role gate — the one that matters**

Requires the new Clerk instance configured: Organizations off, `publicMetadata.role` set on two test users, and a session token customization adding `"role": "{{user.public_metadata.role}}"`.

1. Sign in to `http://localhost:3000` as the user whose `publicMetadata.role` is `user`.
2. From the browser devtools console, take a token: `await window.Clerk.session.getToken()`.
3. Call the guarded endpoint:

```bash
curl -i -H "Authorization: Bearer <token>" http://localhost:8100/api/v1/admin/ping
```

Expected: **403**.

4. Repeat signed in as the `admin` user.

Expected: **200** with `{"ok":true}`.

**If both return 403**, the `role` claim is not on the token — check the session token customization in the Clerk dashboard, not the code. Decode the token at `jwt.io` and confirm a top-level `role` claim is present.

**If both return 401**, the origin is missing from `ALLOWED_ORIGINS` in `server/.env.development` — that is the `azp` check, not a role problem.

- [ ] **Step 5: Final sweep for B2B remnants**

```bash
git grep -Iin "supplier\|org_id\|orgrole\|internal-portal\|project_manager\|reviewer\|approver"
```

Expected: no output.

- [ ] **Step 6: Collapse to a single initial commit**

```bash
git checkout --orphan initial
git add -A
git commit -m "initial commit

Forked from the B2B multi-tenant template at cfca621, with Clerk
Organizations, the supplier example domain and the second portal removed.
The platform role is sourced from Clerk publicMetadata.role and carried on
the session token; there is no database mirror.

See docs/setup/making-it-yours.md to adapt it."
git branch -D main
git branch -m main
git log --oneline
```

Expected: exactly one commit on `main`.

> Replace `cfca621` with the commit recorded in Task 1, Step 1.

- [ ] **Step 7: Confirm the tree survived the orphan branch**

```bash
git status --porcelain
ls web-app/apps
find server/alembic/versions -name '*.py' | wc -l
```

Expected: clean status; `web` is the only app; exactly one migration.

- [ ] **Step 8: Push**

```bash
git push -u origin main
```

Expected: the remote now holds one commit.

---

## Post-fork, not in this plan

- **WS7** (SSE disconnect): `chatbot.py`'s `event_generator()` still never checks for client disconnect. Inherited knowingly.
- **The Traefik labels are unproven**, and this fork changed them. First real Dokploy deploy is the test.
- **The single-Clerk-key build arg** (`Makefile:24`) is correct at one app and silently wrong the day a second app needs a different instance.
- **`web-app/packages/types` has no `tsconfig.json`**, so root `pnpm type-check` skips it. Pre-existing.
