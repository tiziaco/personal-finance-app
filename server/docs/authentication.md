# Authentication System

## Overview

Authentication is handled by [Clerk](https://clerk.com). There are no register/login endpoints — users authenticate via Clerk's hosted UI and the backend validates their JWT tokens. Users are automatically provisioned in the database on first access (JIT provisioning).

## Architecture

```
Request
  |
  v
AuthMiddleware              Extracts JWT, verifies via JWKS (RS256)
  |                         Stores clerk_id in request.state.clerk_id
  v
get_current_user (DI)       JIT provisioning: cache -> DB -> Clerk API
  |                         Stores internal user_id in request.state.user_id
  v
Route Handler               Receives User object via CurrentUser
```

## Dual ID System

| ID | Type | Purpose |
|----|------|---------|
| `id` | UUID string (PK) | Internal DB relationships, foreign keys, RLS context |
| `clerk_id` | Text (unique, indexed) | Auth lookups, Clerk API calls |

All foreign keys (e.g., `conversation.user_id`) reference the internal `id`. The `clerk_id` is only used at the authentication boundary.

## Key Components

### 1. JWT Verification — `app/utils/auth.py`

`ClerkJWTVerifier` uses **PyJWT + JWKS** to verify Clerk-issued tokens:
- Algorithm: **RS256** (asymmetric)
- Keys fetched from `{CLERK_ISSUER}/.well-known/jwks.json`
- JWKS keys cached automatically by `PyJWKClient` (1-hour lifespan)
- Validates `exp` (expiration) and `iss` (issuer) claims

### 2. Auth Middleware — `app/api/middlewares/auth.py`

`AuthMiddleware` runs on every request:
- Extracts Bearer token from `Authorization` header
- Verifies token via `ClerkJWTVerifier`
- Stores `clerk_id` (the JWT `sub` claim) in `request.state.clerk_id`
- **Permissive** — never blocks requests; route dependencies enforce auth

### 3. Auth Dependencies — `app/api/dependencies/auth.py`

Two dependencies, used together:

- **`get_clerk_id(request)`** — reads `clerk_id` from `request.state`; raises `401` if absent
- **`get_current_user(clerk_id, session)`** — resolves `clerk_id` to a `User` object via JIT provisioning; sets `request.state.user_id` to the internal UUID

The type alias `CurrentUser = Annotated[User, Depends(get_current_user)]` is used in route signatures.

### 4. JIT User Provisioning — `app/services/user/service.py`

`UserService.resolve_user(clerk_id, org_id, session)` follows this flow:

1. **DB lookup** — query by `clerk_id` (unique + indexed, so a single index scan)
2. **Clerk API** — fetch user from Clerk, create in DB

Race condition handling: if two concurrent requests try to create the same user, the `IntegrityError` on the unique `clerk_id` constraint is caught, and the existing user is fetched instead.

There is deliberately **no `clerk_id -> user_id` cache**. A hit would still cost one indexed lookup, and FastAPI caches each `Depends` result per request (`use_cache=True` by default), so a single request never resolves the user twice anyway.

### 5. Clerk Client — `app/integrations/clerk/client.py`

`ClerkClient` wraps the `clerk-backend-api` SDK:
- `get_user(clerk_id)` — fetches user data from Clerk API
- `get_primary_email(clerk_user)` — extracts primary email from Clerk user object

Called via `asyncio.to_thread()` since the SDK is synchronous.

### 6. User Repository — `app/services/user/repository.py`

`UserRepository` handles all user DB operations via SQLModel/SQLAlchemy:
- `get_by_id()`, `get_by_clerk_id()`, `get_by_email()`
- `create()` — creates a user from Clerk data
- `update_from_clerk()` — syncs profile changes
- `update_org_id()` — syncs org_id when the JWT's org context changes
- `delete()`

### 7. Supplier Repository — `app/services/user/supplier_repository.py`

`SupplierRepository` handles the `Supplier.contact_id` DB operations used for supplier-linking during JIT provisioning and GDPR erasure:
- `get_by_id()`, `get_by_contact_id()` (any deletion state), `get_id_by_contact_id()` (non-deleted only)
- `set_contact_id()` — links or unlinks a supplier's contact

## In-Memory Caches — `app/services/user/cache.py`

`UserCache` holds two independent caches, backed by `cachetools.TTLCache`:

| Cache | Key → Value | TTL | Why that TTL |
|-------|-------------|-----|--------------|
| `org_role` | `clerk_id -> role` | 60s | Feeds `get_current_role()` → `require_role()`, so a stale entry keeps a revoked permission alive |
| `supplier_id` | `user_id -> supplier_id \| None` | 300s | Saves an indexed query; not authorization-critical |

| Property | Value |
|----------|-------|
| Bounds | `maxsize=10_000` per cache, LRU eviction |
| Scope | Single process — under N workers a TTL is a per-worker staleness bound, not a global one |
| Invalidation | `user_cache.invalidate_user(clerk_id=..., user_id=...)` |

A cached `None` supplier id means "known not linked" and short-circuits the DB, so reads return a `_MISS` sentinel for absence rather than `None`.

Every method is `async` even though the in-memory implementation never awaits — that is the seam for a future Redis backend, so swapping it requires no call-site changes.

**Invalidation points:**
- Supplier re-link (`resolve_user`) — clears both the new contact and the displaced previous one
- GDPR account deletion — clears both caches for the erased user
- Clerk membership webhooks (`app/integrations/clerk/webhooks/handlers/membership.py`) — every `organization_membership.*` event drops the user's cached auth data

The `org_role` staleness this section used to name as an open gap is closed: a role change or an offboarding in Clerk now invalidates the entry on delivery, so revocation is immediate rather than bounded by the 60s TTL. It degrades to the TTL only if the delivery fails every svix retry.

## Swagger UI OAuth2

The `/docs` page has an "Authorize" button that triggers Clerk's OAuth2 Authorization Code flow. Configured in `app/main.py` via `swagger_ui_init_oauth`. Requires:
- `CLERK_OAUTH_CLIENT_ID` from Clerk dashboard (public client — no secret needed, uses PKCE)
- Redirect URI `http://localhost:8000/oauth2-redirect` registered in Clerk's OAuth app settings

## Environment Variables

| Variable | Description |
|----------|-------------|
| `CLERK_SECRET_KEY` | Clerk Backend API secret key |
| `CLERK_ISSUER` | Clerk instance URL (e.g., `https://your-instance.clerk.accounts.dev`) |
| `CLERK_OAUTH_CLIENT_ID` | OAuth app client ID (for Swagger UI) |
| `CLERK_AUTHORIZE_URL` | OAuth authorize endpoint |
| `CLERK_TOKEN_URL` | OAuth token endpoint |
