# Clerk RBAC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the auth and RBAC abstraction layer — org claims extraction, role-gated FastAPI dependencies, `packages/auth` shared library, `AuthProvider`, and fixed `proxy.ts` files — as designed in `docs/superpowers/specs/2026-04-11-clerk-rbac-design.md`.

**Architecture:** Clerk JWTs carry `org_id` and `org_role` claims; the `AuthMiddleware` extracts them into `request.state`; a `Role` enum and `require_role()` factory gate FastAPI endpoints; a new `@rilevio/auth` pnpm package exposes `getUserRole()`, `AuthProvider`, and `useAppAuth()` as the frontend portability seam; both portals' `proxy.ts` files are fixed to read `orgRole` instead of `sessionClaims.metadata.role`.

**Tech Stack:** Python 3.13 / FastAPI / SQLModel / Alembic / pytest — TypeScript 5 / Next.js 16 / React 19 / `@clerk/nextjs` v6 (Core 2) / pnpm workspaces

---

## File Map

### Backend — created / modified

| File | Change |
|------|--------|
| `server/app/models/enums.py` | **Create** — `Role` StrEnum |
| `server/app/models/user.py` | **Modify** — add `org_id: str` field (non-nullable) |
| `server/alembic/versions/` | **Replace** — delete existing migration, generate fresh one |
| `server/app/api/middlewares/auth.py` | **Modify** — extract `org_id` and `org_role` into `request.state` |
| `server/app/services/user/service.py` | **Modify** — add `org_id` param to `create()` |
| `server/app/services/user/provider.py` | **Modify** — pass `org_id` from `request.state` to `get_or_create_user()` |
| `server/app/api/dependencies/auth.py` | **Modify** — add `get_current_role`, `require_role`, `CurrentRole`, convenience aliases |
| `server/tests/unit/middleware/test_auth_middleware.py` | **Modify** — add org claims extraction tests |
| `server/tests/unit/api/test_auth_dependencies.py` | **Create** — tests for `get_current_role` and `require_role` |

### Frontend — created / modified

| File | Change |
|------|--------|
| `web-app/packages/auth/package.json` | **Create** — `@rilevio/auth` package manifest |
| `web-app/packages/auth/tsconfig.json` | **Create** — TypeScript config extending workspace base |
| `web-app/packages/auth/src/permissions.ts` | **Create** — `Role`, `getUserRole`, `isInternalRole`, `ROLE_LABELS` |
| `web-app/packages/auth/src/provider.tsx` | **Create** — `AuthProvider`, `useAppAuth` |
| `web-app/packages/auth/src/index.ts` | **Create** — barrel export |
| `web-app/apps/internal-portal/package.json` | **Modify** — add `@rilevio/auth: workspace:*` |
| `web-app/apps/supplier-portal/package.json` | **Modify** — add `@rilevio/auth: workspace:*` |
| `web-app/apps/internal-portal/app/layout.tsx` | **Modify** — add `AuthProvider` inside `ClerkProvider` |
| `web-app/apps/supplier-portal/app/layout.tsx` | **Modify** — add `AuthProvider` inside `ClerkProvider` |
| `web-app/apps/internal-portal/proxy.ts` | **Modify** — fix role check to use `orgRole` + `getUserRole` |
| `web-app/apps/supplier-portal/proxy.ts` | **Modify** — fix role check to use `orgRole` + `getUserRole` |

---

## Task 1: Role enum

**Files:**
- Create: `server/app/models/enums.py`

- [ ] **Step 1: Write the failing test**

Create `server/tests/unit/models/test_enums.py`:

```python
"""Tests for app.models.enums."""
import pytest
from app.models.enums import Role

pytestmark = pytest.mark.unit


class TestRole:
    def test_all_roles_defined(self):
        assert Role.PROJECT_MANAGER == "project_manager"
        assert Role.REVIEWER == "reviewer"
        assert Role.APPROVER == "approver"
        assert Role.SUPPLIER == "supplier"

    def test_role_from_string(self):
        assert Role("project_manager") == Role.PROJECT_MANAGER

    def test_role_invalid_string_raises(self):
        with pytest.raises(ValueError):
            Role("admin")

    def test_role_is_str(self):
        assert isinstance(Role.PROJECT_MANAGER, str)
```

- [ ] **Step 2: Run test to verify it fails**

Run from `server/`:
```bash
APP_ENV=test uv run pytest tests/unit/models/test_enums.py -v -m unit
```
Expected: `ModuleNotFoundError: No module named 'app.models.enums'`

- [ ] **Step 3: Create `server/app/models/enums.py`**

```python
"""Domain enumerations for the Rilevio application."""

from enum import StrEnum


class Role(StrEnum):
    """Clerk organisation roles.

    Values match the Clerk org role slugs with the 'org:' prefix stripped.
    The AuthMiddleware extracts org_role from the JWT and strips the prefix
    before storing it in request.state.org_role.

    Migration note: when switching auth providers, only AuthMiddleware changes.
    This enum and all consumers remain unchanged.
    """

    PROJECT_MANAGER = "project_manager"
    REVIEWER = "reviewer"
    APPROVER = "approver"
    SUPPLIER = "supplier"
```

- [ ] **Step 4: Run test to verify it passes**

```bash
APP_ENV=test uv run pytest tests/unit/models/test_enums.py -v -m unit
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add server/app/models/enums.py server/tests/unit/models/test_enums.py
git commit -m "feat(server): add Role StrEnum for org-based RBAC"
```

---

## Task 2: Extend AuthMiddleware to extract org claims

**Files:**
- Modify: `server/app/api/middlewares/auth.py`
- Modify: `server/tests/unit/middleware/test_auth_middleware.py`

- [ ] **Step 1: Write the failing tests**

Add to `server/tests/unit/middleware/test_auth_middleware.py` — replace the existing `_make_app` helper and `TestAuthMiddleware` class with the version below (keep existing tests, add new ones):

```python
"""Tests for app.api.middlewares.auth — token extraction and permissive pass-through."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.api.middlewares.auth import AuthMiddleware

pytestmark = pytest.mark.unit


def _make_app():
    """Create a minimal Starlette app with AuthMiddleware for testing."""

    async def endpoint(request: Request):
        return JSONResponse({
            "clerk_id": getattr(request.state, "clerk_id", None),
            "user_id": getattr(request.state, "user_id", None),
            "org_id": getattr(request.state, "org_id", None),
            "org_role": getattr(request.state, "org_role", None),
        })

    app = Starlette(routes=[Route("/test", endpoint)])
    app.add_middleware(AuthMiddleware)
    return app


@pytest.fixture
def app():
    return _make_app()


class TestAuthMiddleware:
    """Tests for AuthMiddleware.dispatch()."""

    @pytest.mark.asyncio
    @patch("app.api.middlewares.auth.clerk_jwt_verifier")
    async def test_valid_bearer_sets_clerk_id(self, mock_verifier, app):
        mock_verifier.verify_token.return_value = {"sub": "user_abc123"}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/test", headers={"Authorization": "Bearer valid.token"})

        assert response.status_code == 200
        assert response.json()["clerk_id"] == "user_abc123"

    @pytest.mark.asyncio
    async def test_missing_auth_header_passes_through(self, app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/test")

        assert response.status_code == 200
        assert response.json()["clerk_id"] is None

    @pytest.mark.asyncio
    @patch("app.api.middlewares.auth.clerk_jwt_verifier")
    async def test_invalid_token_clerk_id_none(self, mock_verifier, app):
        mock_verifier.verify_token.return_value = None

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/test", headers={"Authorization": "Bearer bad.token"})

        assert response.status_code == 200
        assert response.json()["clerk_id"] is None

    @pytest.mark.asyncio
    async def test_non_bearer_auth_header_ignored(self, app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/test", headers={"Authorization": "Basic dXNlcjpwYXNz"})

        assert response.status_code == 200
        assert response.json()["clerk_id"] is None

    @pytest.mark.asyncio
    async def test_bearer_without_token_clerk_id_none(self, app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/test", headers={"Authorization": "Bearer "})

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_user_id_defaults_to_none(self, app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/test")

        assert response.json()["user_id"] is None

    # --- NEW: org claims ---

    @pytest.mark.asyncio
    @patch("app.api.middlewares.auth.clerk_jwt_verifier")
    async def test_org_claims_extracted_from_token(self, mock_verifier, app):
        mock_verifier.verify_token.return_value = {
            "sub": "user_abc123",
            "org_id": "org_xyz",
            "org_role": "org:project_manager",
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/test", headers={"Authorization": "Bearer valid.token"})

        data = response.json()
        assert data["org_id"] == "org_xyz"
        assert data["org_role"] == "project_manager"  # prefix stripped

    @pytest.mark.asyncio
    @patch("app.api.middlewares.auth.clerk_jwt_verifier")
    async def test_org_prefix_stripped(self, mock_verifier, app):
        """'org:supplier' should be stored as 'supplier'."""
        mock_verifier.verify_token.return_value = {
            "sub": "user_s1",
            "org_id": "org_abc",
            "org_role": "org:supplier",
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/test", headers={"Authorization": "Bearer token"})

        assert response.json()["org_role"] == "supplier"

    @pytest.mark.asyncio
    @patch("app.api.middlewares.auth.clerk_jwt_verifier")
    async def test_missing_org_claims_are_none(self, mock_verifier, app):
        """Token with no org context (personal account or not-yet-selected org)."""
        mock_verifier.verify_token.return_value = {"sub": "user_abc123"}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/test", headers={"Authorization": "Bearer valid.token"})

        data = response.json()
        assert data["org_id"] is None
        assert data["org_role"] is None
```

- [ ] **Step 2: Run tests to verify the new ones fail**

```bash
APP_ENV=test uv run pytest tests/unit/middleware/test_auth_middleware.py -v -m unit
```
Expected: existing tests pass, 3 new tests fail (`org_id` and `org_role` keys not present in response).

- [ ] **Step 3: Update `server/app/api/middlewares/auth.py`**

```python
"""Authentication middleware for Clerk JWT token extraction and verification."""

from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.logging import logger
from app.utils.auth import clerk_jwt_verifier


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware for extracting and verifying Clerk JWT tokens.

    Stores the following in request.state after a valid token:
      - clerk_id  : Clerk user ID (sub claim)
      - org_id    : Clerk organisation ID (org_id claim), or None
      - org_role  : Role slug with 'org:' prefix stripped (org_role claim), or None

    The middleware is permissive — it does not block requests with invalid/missing
    tokens. Route-level dependencies determine if authentication is required.

    Note: after user provisioning, request.state.user_id is set to the internal UUID.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request.state.clerk_id = None
        request.state.user_id = None
        request.state.org_id = None
        request.state.org_role = None

        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            try:
                token = auth_header.split(" ")[1]
                payload = clerk_jwt_verifier.verify_token(token)

                if payload:
                    request.state.clerk_id = payload.get("sub")
                    request.state.org_id = payload.get("org_id")
                    # Strip 'org:' prefix: "org:project_manager" → "project_manager"
                    raw_role = payload.get("org_role", "") or ""
                    request.state.org_role = raw_role.removeprefix("org:") or None

                    logger.debug(
                        "token_verified_in_middleware",
                        clerk_id=request.state.clerk_id,
                        org_id=request.state.org_id,
                        org_role=request.state.org_role,
                        path=request.url.path,
                    )
                else:
                    logger.debug("token_verification_failed_in_middleware", path=request.url.path)

            except (IndexError, ValueError) as e:
                logger.debug("token_extraction_failed", error=str(e), path=request.url.path)
        else:
            logger.debug("no_auth_header_present", path=request.url.path)

        response = await call_next(request)
        return response
```

- [ ] **Step 4: Run all middleware tests**

```bash
APP_ENV=test uv run pytest tests/unit/middleware/test_auth_middleware.py -v -m unit
```
Expected: all tests pass (existing + 3 new).

- [ ] **Step 5: Commit**

```bash
git add server/app/api/middlewares/auth.py server/tests/unit/middleware/test_auth_middleware.py
git commit -m "feat(server): extract org_id and org_role from JWT in AuthMiddleware"
```

---

## Task 3: Add role dependencies to FastAPI

**Files:**
- Modify: `server/app/api/dependencies/auth.py`
- Create: `server/tests/unit/api/test_auth_dependencies.py`

- [ ] **Step 1: Write the failing tests**

Create `server/tests/unit/api/test_auth_dependencies.py`:

```python
"""Tests for role-based dependencies in app.api.dependencies.auth."""

import pytest
from unittest.mock import MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies.auth import get_current_role, require_role
from app.exceptions.base import AuthorizationError
from app.models.enums import Role

pytestmark = pytest.mark.unit


def _make_request_with_role(role: str | None):
    """Create a mock Request with org_role in state."""
    request = MagicMock()
    request.state.org_role = role
    return request


class TestGetCurrentRole:
    def test_returns_role_enum_for_valid_role(self):
        request = _make_request_with_role("project_manager")
        result = get_current_role(request)
        assert result == Role.PROJECT_MANAGER

    def test_returns_supplier_role(self):
        request = _make_request_with_role("supplier")
        result = get_current_role(request)
        assert result == Role.SUPPLIER

    def test_raises_authorization_error_when_no_role(self):
        request = _make_request_with_role(None)
        with pytest.raises(AuthorizationError, match="No organization role"):
            get_current_role(request)

    def test_raises_authorization_error_for_unknown_role(self):
        request = _make_request_with_role("unknown_role")
        with pytest.raises(AuthorizationError, match="Unknown role"):
            get_current_role(request)


class TestRequireRole:
    """Integration tests using a minimal FastAPI app."""

    def _make_app(self, *allowed: Role):
        app = FastAPI()

        @app.get("/protected", dependencies=[require_role(*allowed)])
        def protected():
            return {"ok": True}

        return TestClient(app, raise_server_exceptions=False)

    def test_allowed_role_passes(self):
        client = self._make_app(Role.PROJECT_MANAGER, Role.REVIEWER)

        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(
                "app.api.dependencies.auth.get_current_role",
                lambda req: Role.PROJECT_MANAGER,
            )
            # Use override instead of monkeypatching for FastAPI dependency
        # Re-test via override
        app = FastAPI()

        async def _override():
            return Role.PROJECT_MANAGER

        from app.api.dependencies.auth import get_current_role as gcr
        app.dependency_overrides[gcr] = _override

        @app.get("/protected", dependencies=[require_role(Role.PROJECT_MANAGER)])
        def protected():
            return {"ok": True}

        client = TestClient(app)
        response = client.get("/protected")
        assert response.status_code == 200

    def test_disallowed_role_raises_403(self):
        app = FastAPI()

        async def _override():
            return Role.SUPPLIER

        from app.api.dependencies.auth import get_current_role as gcr
        app.dependency_overrides[gcr] = _override

        @app.get("/protected", dependencies=[require_role(Role.PROJECT_MANAGER)])
        def protected():
            return {"ok": True}

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/protected")
        assert response.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
APP_ENV=test uv run pytest tests/unit/api/test_auth_dependencies.py -v -m unit
```
Expected: `ImportError` — `get_current_role` and `require_role` not yet defined.

- [ ] **Step 3: Update `server/app/api/dependencies/auth.py`**

```python
"""Authentication dependencies for FastAPI endpoints."""

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import OAuth2AuthorizationCodeBearer

from app.api.dependencies.database import DbSession
from app.core.config import settings
from app.core.logging import bind_context, logger
from app.exceptions.base import AuthenticationError, AuthorizationError
from app.models.enums import Role
from app.models.user import User
from app.services.user import user_provider

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
        org_id = getattr(request.state, "org_id", None)
        user = await user_provider.get_or_create_user(clerk_id, org_id, session)
        request.state.user_id = user.id
        bind_context(user_id=user.id)
    except Exception as e:
        logger.error("user_provisioning_failed", clerk_id=clerk_id, error=str(e))
        raise AuthenticationError("Failed to provision user") from e
    return user


def get_current_role(request: Request) -> Role:
    """Extract the org role from request.state (set by AuthMiddleware).

    This is the backend portability seam. When migrating to WorkOS or a
    DB-backed role table, only this function changes — all endpoints and
    require_role() calls remain unchanged.

    Raises:
        AuthorizationError: If no org role is present or the role is unrecognised.
    """
    raw = getattr(request.state, "org_role", None)
    if not raw:
        raise AuthorizationError("No organization role in token")
    try:
        return Role(raw)
    except ValueError:
        raise AuthorizationError(f"Unknown role: {raw}")


def require_role(*allowed: Role):
    """Dependency factory that enforces one of the allowed roles.

    Usage:
        @router.get("/projects", dependencies=[InternalUserRole])
        async def list_projects(user: CurrentUser, ...): ...

    Args:
        *allowed: One or more Role values that are permitted.

    Returns:
        A FastAPI Depends object suitable for use in the dependencies list.
    """
    def dependency(role: Role = Depends(get_current_role)) -> None:
        if role not in allowed:
            raise AuthorizationError(
                f"Role '{role}' is not permitted. Required: {[r.value for r in allowed]}"
            )
    return Depends(dependency)


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

# Authenticated user — use in endpoint signatures
CurrentUser = Annotated[User, Depends(get_current_user)]

# Current role — use when you need the role value in endpoint logic
CurrentRole = Annotated[Role, Depends(get_current_role)]

# ---------------------------------------------------------------------------
# Role guards — use in endpoint `dependencies=[...]` list
# ---------------------------------------------------------------------------

# Any internal user (not a supplier)
InternalUserRole = require_role(Role.PROJECT_MANAGER, Role.REVIEWER, Role.APPROVER)

# Project managers only
PMOnly = require_role(Role.PROJECT_MANAGER)

# Reviewers and project managers (can review documents)
ReviewerRole = require_role(Role.PROJECT_MANAGER, Role.REVIEWER)

# Suppliers only
SupplierRole = require_role(Role.SUPPLIER)
```

- [ ] **Step 4: Run tests**

```bash
APP_ENV=test uv run pytest tests/unit/api/test_auth_dependencies.py -v -m unit
```
Expected: all tests pass.

- [ ] **Step 5: Run full unit suite to check for regressions**

```bash
APP_ENV=test uv run pytest tests/unit/ -v -m unit
```
Expected: all existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add server/app/api/dependencies/auth.py server/tests/unit/api/test_auth_dependencies.py
git commit -m "feat(server): add get_current_role, require_role, and role guard aliases"
```

---

## Task 4: Add `org_id` to User model and generate migration

**Files:**
- Modify: `server/app/models/user.py`
- Create: `server/alembic/versions/<rev>_add_org_id_to_users.py` (auto-generated)

- [ ] **Step 1: Update `server/app/models/user.py`** — add `org_id` field

```python
"""This file contains the user model for the application."""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime
from sqlmodel import Field, Relationship

from app.models.base import AnonymizableMixin, BaseModel

if TYPE_CHECKING:
    from app.models.conversation import Conversation


class User(BaseModel, AnonymizableMixin, table=True):
    """User model for storing user accounts.

    GDPR Compliance:
    - When user requests deletion, use anonymize_user() to clear personal data
    - Keep the record ID for referential integrity (conversations, etc.)
    - Mark with anonymized_at timestamp

    Attributes:
        id: Internal UUID primary key for DB relationships
        clerk_id: External Clerk user ID for auth lookups (anonymized on deletion)
        org_id: Clerk organisation ID. Set from JWT on every login; used for
            tenant-scoped DB queries. Intentionally not the role (see design spec).
        email: User's email address (anonymized on deletion)
        email_verified: Whether the email is verified in Clerk
        first_name: User's first name from Clerk (anonymized on deletion)
        last_name: User's last name from Clerk (anonymized on deletion)
        avatar_url: User's avatar URL from Clerk (anonymized on deletion)
        last_synced_at: Last time data was synced from Clerk
        created_at: When the user was created (from BaseModel)
        updated_at: Last time the record was updated (auto-managed by BaseModel)
        anonymized_at: When personal data was anonymized (GDPR deletion)
        conversations: Relationship to user's chat conversations
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    clerk_id: str = Field(unique=True, index=True)
    org_id: str = Field(index=True)
    email: str = Field(unique=True, index=True)
    email_verified: bool = Field(default=False)
    first_name: Optional[str] = Field(default=None)
    last_name: Optional[str] = Field(default=None)
    avatar_url: Optional[str] = Field(default=None)
    last_synced_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_type=DateTime(timezone=True),
        nullable=False,
    )
    conversations: List["Conversation"] = Relationship(back_populates="user")

    def anonymize_user(self) -> None:
        """Anonymize user personal data for GDPR compliance."""
        anonymous_id = f"deleted_user_{self.id[:8]}"
        self.clerk_id = anonymous_id
        self.email = f"{anonymous_id}@anonymized.local"
        self.email_verified = False
        self.first_name = None
        self.last_name = None
        self.avatar_url = None
        self.org_id = None

        for conversation in self.conversations:
            conversation.name = ""

        self.mark_anonymized()


# Avoid circular imports
from app.models.conversation import Conversation  # noqa: E402
```

- [ ] **Step 2: Delete the existing migration and generate a fresh one**

No existing data — drop the old migration and regenerate from the current model state:

```bash
# Delete the existing migration
rm server/alembic/versions/20260218_0000_1a2b3c4d5e6f_initial_database.py
```

Start the database if not running (from repo root):
```bash
make docker-run-db ENV=development
```

Drop and recreate the schema so Alembic starts from a clean slate:
```bash
# Connect to the DB and reset (adjust credentials from .env.development)
docker exec -it rilevio-db psql -U <user> -d <db> -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
```

Generate the fresh migration from `server/`:
```bash
make migrate-create ENV=development MSG="initial schema"
```

Open the generated file and verify `upgrade()` includes:
```python
op.create_table('user',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('clerk_id', sa.String(), nullable=False),
    sa.Column('org_id', sa.String(), nullable=False),
    sa.Column('email', sa.String(), nullable=False),
    ...
)
op.create_index(op.f('ix_user_org_id'), 'user', ['org_id'], unique=False)
```

`org_id` must be `nullable=False`. If autogenerate produced `nullable=True`, correct it manually.

- [ ] **Step 3: Apply the migration**

```bash
make migrate ENV=development
```
Expected: `Running upgrade  -> <rev>, initial schema`

- [ ] **Step 4: Commit**

```bash
git add server/app/models/user.py server/alembic/versions/
git commit -m "feat(server): add org_id (non-nullable) to User model, replace initial migration"
```

---

## Task 5: Update UserRepository and UserProvider to persist `org_id`

**Files:**
- Modify: `server/app/services/user/service.py`
- Modify: `server/app/services/user/provider.py`

- [ ] **Step 1: Update `server/app/services/user/service.py`** — add `org_id` to `create()`

In `UserRepository.create()`, add `org_id` parameter and pass it to the `User` constructor:

```python
@staticmethod
async def create(
    session: AsyncSession,
    clerk_id: str,
    email: str,
    org_id: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    avatar_url: Optional[str] = None,
    email_verified: bool = False,
) -> User:
    """Create a new user from Clerk data.

    Args:
        session: Database session
        clerk_id: Clerk user ID
        email: User's email address
        org_id: Clerk organisation ID (from JWT org_id claim)
        first_name: User's first name
        last_name: User's last name
        avatar_url: User's avatar URL
        email_verified: Whether the email is verified

    Returns:
        The created User.
    """
    user = User(
        clerk_id=clerk_id,
        email=email,
        org_id=org_id,
        first_name=first_name,
        last_name=last_name,
        avatar_url=avatar_url,
        email_verified=email_verified,
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)

    logger.info("user_created", user_id=user.id, clerk_id=clerk_id, email=email, org_id=org_id)
    return user
```

- [ ] **Step 2: Update `server/app/services/user/provider.py`** — accept and pass `org_id`

Replace `get_or_create_user` with the version below. The signature adds `org_id: Optional[str]` and passes it through to `user_repository.create()`. It also upserts `org_id` on the user record on every call (handles the case where an admin moves a user to a different org):

```python
async def get_or_create_user(
    self,
    clerk_id: str,
    org_id: str,
    session: AsyncSession,
) -> User:
    """Get a user by clerk_id, creating them via JIT provisioning if needed.

    Updates org_id on every call so the DB stays in sync if the user's org
    changes (e.g. admin re-assigns to a different organisation).

    Args:
        clerk_id: The Clerk user ID.
        org_id: The Clerk organisation ID from the JWT.
        session: Database session for DB operations.

    Returns:
        The User object (attached to the current session).

    Raises:
        RuntimeError: If user cannot be provisioned from Clerk.
    """
    # 1. Check cache for clerk_id -> user_id mapping
    if cached_user_id := self._get_from_cache(clerk_id):
        user = await user_repository.get_by_id(session, cached_user_id)
        if user:
            # Keep org_id in sync even on cache hits
            if user.org_id != org_id:
                user.org_id = org_id
                session.add(user)
                await session.flush()
            return user
        self.invalidate_cache(clerk_id)

    # 2. Check DB by clerk_id
    user = await user_repository.get_by_clerk_id(session, clerk_id)
    if user:
        if user.org_id != org_id:
            user.org_id = org_id
            session.add(user)
            await session.flush()
        self._set_cache(clerk_id, user.id)
        return user

    # 3. JIT: Fetch from Clerk and create in DB
    logger.info("jit_provisioning_user", clerk_id=clerk_id)

    try:
        clerk_user = await asyncio.to_thread(clerk_service.get_user, clerk_id)
    except ClerkUserNotFoundError:
        logger.error("clerk_user_not_found_during_provisioning", clerk_id=clerk_id)
        raise

    email = clerk_service.get_primary_email(clerk_user)
    if not email:
        logger.error("clerk_user_missing_email", clerk_id=clerk_id)
        raise RuntimeError(f"No email found for Clerk user {clerk_id}")

    try:
        user = await user_repository.create(
            session=session,
            clerk_id=clerk_id,
            email=email,
            org_id=org_id,
            first_name=clerk_user.first_name,
            last_name=clerk_user.last_name,
            avatar_url=clerk_user.image_url,
            email_verified=bool(clerk_user.primary_email_address_id),
        )
    except IntegrityError:
        await session.rollback()
        logger.info("jit_provisioning_race_resolved", clerk_id=clerk_id)
        user = await user_repository.get_by_clerk_id(session, clerk_id)
        if not user:
            raise RuntimeError(f"Failed to provision user {clerk_id}")

    self._set_cache(clerk_id, user.id)
    return user
```

- [ ] **Step 3: Run unit tests to confirm no regressions**

```bash
APP_ENV=test uv run pytest tests/unit/ -v -m unit
```
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add server/app/services/user/service.py server/app/services/user/provider.py
git commit -m "feat(server): persist org_id on User via JIT provisioning"
```

---

## Task 6: Create `packages/auth` — scaffold and permissions

**Files:**
- Create: `web-app/packages/auth/package.json`
- Create: `web-app/packages/auth/tsconfig.json`
- Create: `web-app/packages/auth/src/permissions.ts`
- Create: `web-app/packages/auth/src/index.ts`

- [ ] **Step 1: Create `web-app/packages/auth/package.json`**

```json
{
  "name": "@rilevio/auth",
  "version": "0.0.1",
  "private": true,
  "main": "./src/index.ts",
  "types": "./src/index.ts",
  "exports": {
    ".": "./src/index.ts"
  },
  "peerDependencies": {
    "@clerk/nextjs": ">=6.0.0",
    "@clerk/types": ">=4.0.0",
    "react": "^19.0.0"
  },
  "devDependencies": {
    "@types/react": "^19.2.14",
    "typescript": "^5.9.3"
  }
}
```

- [ ] **Step 2: Create `web-app/packages/auth/tsconfig.json`**

```json
{
  "extends": "../../tsconfig.json",
  "compilerOptions": {
    "outDir": "dist"
  },
  "include": ["src"]
}
```

Note: if `web-app/tsconfig.json` does not exist at workspace root, use the internal-portal's tsconfig as a reference and create a minimal one:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true
  }
}
```

- [ ] **Step 3: Create `web-app/packages/auth/src/permissions.ts`**

```typescript
/**
 * Role definitions and utilities for Rilevio RBAC.
 *
 * Portability seam: getUserRole() is the only function that knows how
 * the auth provider represents roles. When migrating to WorkOS, only
 * this function changes — all consumers remain unchanged.
 */

/** Clerk org role slugs with the 'org:' prefix stripped. */
export const Role = {
  PROJECT_MANAGER: "project_manager",
  REVIEWER: "reviewer",
  APPROVER: "approver",
  SUPPLIER: "supplier",
} as const

export type Role = (typeof Role)[keyof typeof Role]

/**
 * Convert a Clerk orgRole string to a Role value.
 *
 * Strips the 'org:' prefix that Clerk adds to all org role slugs.
 * Returns null if orgRole is absent (user has no active org context).
 *
 * @example
 * getUserRole("org:project_manager") // → "project_manager"
 * getUserRole(null)                  // → null
 */
export function getUserRole(orgRole: string | null | undefined): Role | null {
  if (!orgRole) return null
  const stripped = orgRole.replace("org:", "")
  const values = Object.values(Role) as string[]
  if (!values.includes(stripped)) return null
  return stripped as Role
}

/** Returns true for any role that grants access to the internal portal. */
export function isInternalRole(role: Role | null): boolean {
  return role !== null && role !== Role.SUPPLIER
}

/** Italian display labels — mapped in the frontend only. */
export const ROLE_LABELS: Record<Role, string> = {
  [Role.PROJECT_MANAGER]: "Project Manager",
  [Role.REVIEWER]: "Revisore",
  [Role.APPROVER]: "Approvatore",
  [Role.SUPPLIER]: "Fornitore",
}
```

- [ ] **Step 4: Create `web-app/packages/auth/src/index.ts`** (barrel — provider added in Task 7)

```typescript
export * from "./permissions"
```

- [ ] **Step 5: Add `@rilevio/auth` to both app `package.json` files**

In `web-app/apps/internal-portal/package.json`, add to `dependencies`:
```json
"@rilevio/auth": "workspace:*"
```

In `web-app/apps/supplier-portal/package.json`, add to `dependencies`:
```json
"@rilevio/auth": "workspace:*"
```

- [ ] **Step 6: Install workspace packages**

Run from `web-app/`:
```bash
pnpm install
```

- [ ] **Step 7: Type-check**

Run from `web-app/`:
```bash
pnpm type-check
```
Expected: no errors related to `@rilevio/auth`.

- [ ] **Step 8: Commit**

```bash
git add web-app/packages/auth/ web-app/apps/internal-portal/package.json web-app/apps/supplier-portal/package.json web-app/pnpm-lock.yaml
git commit -m "feat(auth): create @rilevio/auth package with Role, getUserRole, ROLE_LABELS"
```

---

## Task 7: Add `AuthProvider` and `useAppAuth` to `packages/auth`

**Files:**
- Create: `web-app/packages/auth/src/provider.tsx`
- Modify: `web-app/packages/auth/src/index.ts`

- [ ] **Step 1: Create `web-app/packages/auth/src/provider.tsx`**

```tsx
/**
 * AuthProvider and useAppAuth hook.
 *
 * Portability seam: AuthProvider wraps Clerk's hooks to derive identity and role.
 * When migrating to WorkOS, only AuthProvider's internals change.
 * All components call useAppAuth() — they never call useAuth() or useUser() directly.
 */
"use client"

import { createContext, useContext } from "react"
import { useAuth, useUser } from "@clerk/nextjs"
import type { UserResource } from "@clerk/types"
import { getUserRole, Role } from "./permissions"

interface AuthContextValue {
  /** The Clerk user object, or null/undefined while loading. */
  user: UserResource | null | undefined
  /** The current user's org role, or null if no active org context. */
  role: Role | null
  /** True once Clerk has finished initialising the session. */
  isLoaded: boolean
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  role: null,
  isLoaded: false,
})

/**
 * Wrap inside ClerkProvider in each app's root layout.
 *
 * @example
 * // app/layout.tsx
 * <ClerkProvider>
 *   <AuthProvider>
 *     {children}
 *   </AuthProvider>
 * </ClerkProvider>
 */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { isLoaded, orgRole } = useAuth()
  const { user } = useUser()
  const role = getUserRole(orgRole)

  return (
    <AuthContext.Provider value={{ user, role, isLoaded }}>
      {children}
    </AuthContext.Provider>
  )
}

/**
 * Hook for accessing the current user's identity and role.
 *
 * Rules:
 * - Never call useAuth() or useUser() directly in components.
 * - Always check isLoaded before rendering role-dependent UI.
 *
 * @example
 * const { user, role, isLoaded } = useAppAuth()
 * if (!isLoaded) return <Skeleton />
 * if (role === Role.PROJECT_MANAGER) { ... }
 */
export function useAppAuth(): AuthContextValue {
  return useContext(AuthContext)
}
```

- [ ] **Step 2: Update `web-app/packages/auth/src/index.ts`**

```typescript
export * from "./permissions"
export { AuthProvider, useAppAuth } from "./provider"
```

- [ ] **Step 3: Type-check**

```bash
cd web-app && pnpm type-check
```
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add web-app/packages/auth/src/provider.tsx web-app/packages/auth/src/index.ts
git commit -m "feat(auth): add AuthProvider and useAppAuth hook to @rilevio/auth"
```

---

## Task 8: Wire `AuthProvider` into app root layouts

**Files:**
- Modify: `web-app/apps/internal-portal/app/layout.tsx`
- Modify: `web-app/apps/supplier-portal/app/layout.tsx`

- [ ] **Step 1: Update `web-app/apps/internal-portal/app/layout.tsx`**

```tsx
import { Inter } from "next/font/google"
import { ThemeProvider } from "@rilevio/ui/theme-provider"
import { Toaster } from "@rilevio/ui/sonner"
import { ClerkProvider } from "@clerk/nextjs"
import { AuthProvider } from "@rilevio/auth"
import { QueryProvider } from "@/providers/query-provider"

import type { Metadata } from "next"
import "@/styles/globals.css"

const inter = Inter({ subsets: ["latin"], variable: "--font-sans" })

export const metadata: Metadata = {
  title: "Fullstack Template",
  description:
    "Fullstack template project using Next.js, Tailwind CSS, and Clerk for authentication.",
  icons: {
    icon: [
      { url: "/icons/favicon.ico", sizes: "any", type: "image/x-icon" },
      { url: "/icons/favicon-16x16.ico", sizes: "16x16", type: "image/x-icon" },
      { url: "/icons/favicon-32x32.ico", sizes: "32x32", type: "image/x-icon" },
    ],
    apple: [{ url: "/icons/favicon-ios-57x57.ico", sizes: "57x57" }],
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <ClerkProvider>
      <html lang="en" suppressHydrationWarning className={inter.variable}>
        <body className="antialiased min-h-screen bg-background">
          <AuthProvider>
            <QueryProvider>
              <ThemeProvider
                attribute="class"
                defaultTheme="system"
                enableSystem
                disableTransitionOnChange
              >
                {children}
                <Toaster position="bottom-right" />
              </ThemeProvider>
            </QueryProvider>
          </AuthProvider>
        </body>
      </html>
    </ClerkProvider>
  )
}
```

- [ ] **Step 2: Update `web-app/apps/supplier-portal/app/layout.tsx`**

Read the current file first to see what's there, then add `AuthProvider` in the same position — inside `ClerkProvider`, wrapping the body content. The pattern is identical to the internal portal above: `<ClerkProvider> → <html> → <body> → <AuthProvider> → ...`.

- [ ] **Step 3: Type-check**

```bash
cd web-app && pnpm type-check
```
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add web-app/apps/internal-portal/app/layout.tsx web-app/apps/supplier-portal/app/layout.tsx
git commit -m "feat(portals): wire AuthProvider into root layouts"
```

---

## Task 9: Fix `proxy.ts` — internal portal

**Files:**
- Modify: `web-app/apps/internal-portal/proxy.ts`

The current file reads `sessionClaims.metadata.role` (user metadata, not org role) and checks for the hardcoded string `"internal"` — both are wrong.

- [ ] **Step 1: Replace `web-app/apps/internal-portal/proxy.ts`**

```typescript
import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server"
import { NextResponse } from "next/server"
import { getUserRole, isInternalRole } from "@rilevio/auth"

const isPublicRoute = createRouteMatcher(["/sign-in(.*)", "/sign-up(.*)"])

export default clerkMiddleware(async (auth, req) => {
  // Allow public routes (sign-in, sign-up) without auth
  if (isPublicRoute(req)) return

  // Enforce authentication
  await auth.protect()

  // Enforce internal-portal access: project_manager, reviewer, or approver only.
  // orgRole is null if the user has no active org (e.g. mid-invitation flow).
  const { orgRole } = await auth()
  const role = getUserRole(orgRole)

  if (!role || !isInternalRole(role)) {
    return NextResponse.redirect(new URL("/unauthorized", req.url))
  }
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

- [ ] **Step 2: Type-check**

```bash
cd web-app && pnpm type-check
```
Expected: no errors.

- [ ] **Step 3: Smoke-test manually**

Start the internal portal:
```bash
cd web-app && pnpm dev:internal
```
- Navigate to `http://localhost:3000` — you should be redirected to `/sign-in`
- Sign in with a user who has `org:project_manager` role → should land on the app
- Sign in with a user who has `org:supplier` role → should be redirected to `/unauthorized`

- [ ] **Step 4: Commit**

```bash
git add web-app/apps/internal-portal/proxy.ts
git commit -m "fix(internal-portal): use orgRole from Clerk session instead of sessionClaims.metadata"
```

---

## Task 10: Fix `proxy.ts` — supplier portal

**Files:**
- Modify: `web-app/apps/supplier-portal/proxy.ts`

The current supplier portal `proxy.ts` has the same bug as the internal portal AND has the wrong role check (it blocks suppliers, not allows them).

- [ ] **Step 1: Replace `web-app/apps/supplier-portal/proxy.ts`**

```typescript
import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server"
import { NextResponse } from "next/server"
import { getUserRole, Role } from "@rilevio/auth"

const isPublicRoute = createRouteMatcher(["/sign-in(.*)", "/sign-up(.*)"])

export default clerkMiddleware(async (auth, req) => {
  // Allow public routes (sign-in, sign-up) without auth
  if (isPublicRoute(req)) return

  // Enforce authentication
  await auth.protect()

  // Enforce supplier-portal access: supplier role only.
  // Internal users (PM, reviewer, approver) are blocked here.
  const { orgRole } = await auth()
  const role = getUserRole(orgRole)

  if (role !== Role.SUPPLIER) {
    return NextResponse.redirect(new URL("/unauthorized", req.url))
  }
})

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
}
```

- [ ] **Step 2: Type-check**

```bash
cd web-app && pnpm type-check
```
Expected: no errors.

- [ ] **Step 3: Smoke-test manually**

Start the supplier portal:
```bash
cd web-app && pnpm dev:supplier
```
- Navigate to `http://localhost:3002` — should redirect to `/sign-in`
- Sign in with a user who has `org:supplier` role → should land on the app
- Sign in with a user who has `org:project_manager` role → should redirect to `/unauthorized`

- [ ] **Step 4: Commit**

```bash
git add web-app/apps/supplier-portal/proxy.ts
git commit -m "fix(supplier-portal): gate on supplier role using orgRole from Clerk session"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| Clerk Dashboard setup (manual, no code) | — |
| `AuthMiddleware` extracts `org_id` and `org_role` | Task 2 |
| `Role` StrEnum | Task 1 |
| `get_current_role` dependency | Task 3 |
| `require_role` factory + aliases | Task 3 |
| `org_id` added to `User` model | Task 4 |
| Alembic migration for `org_id` | Task 4 |
| `UserRepository.create` accepts `org_id` | Task 5 |
| `UserProvider.get_or_create_user` passes `org_id` | Task 5 |
| `packages/auth` (`@rilevio/auth`) created | Task 6 |
| `getUserRole`, `isInternalRole`, `ROLE_LABELS` | Task 6 |
| `AuthProvider` + `useAppAuth` | Task 7 |
| Both layouts wire `AuthProvider` | Task 8 |
| Internal portal `proxy.ts` reads `orgRole` | Task 9 |
| Supplier portal `proxy.ts` reads `orgRole` + checks `Role.SUPPLIER` | Task 10 |

All spec requirements covered. No placeholders remain.
