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

### 4. JIT User Provisioning — `app/services/user/provider.py`

`UserProvider.get_or_create_user(clerk_id, session)` follows this flow:

1. **Cache hit** — in-memory `clerk_id -> user_id` mapping (5-min TTL), then fetch from DB by `user_id`
2. **DB lookup** — query by `clerk_id`
3. **Clerk API** — fetch user from Clerk, create in DB, cache the mapping

Race condition handling: if two concurrent requests try to create the same user, the `IntegrityError` on the unique `clerk_id` constraint is caught, and the existing user is fetched instead.

The cache stores only `clerk_id -> user_id` strings (not ORM objects) to avoid detached session issues.

### 5. Clerk Service — `app/services/clerk.py`

`ClerkService` wraps the `clerk-backend-api` SDK:
- `get_user(clerk_id)` — fetches user data from Clerk API
- `get_primary_email(clerk_user)` — extracts primary email from Clerk user object

Called via `asyncio.to_thread()` since the SDK is synchronous.

### 6. User Repository — `app/services/user/service.py`

`UserRepository` handles all user DB operations via SQLModel/SQLAlchemy:
- `get_by_id()`, `get_by_clerk_id()`, `get_by_email()`
- `create()` — creates a user from Clerk data
- `update_from_clerk()` — syncs profile changes
- `delete()`

## In-Memory Cache

| Property | Value |
|----------|-------|
| Storage | Python dict (`clerk_id -> (user_id, timestamp)`) |
| TTL | 5 minutes |
| Scope | Single process (not shared across workers) |
| Invalidation | `UserProvider.invalidate_cache(clerk_id)` / `clear_cache()` |

**Performance**: cached requests skip the Clerk API call and do a single DB lookup by primary key.

## Swagger UI OAuth2

The `/docs` page has an "Authorize" button that triggers Clerk's OAuth2 Authorization Code flow. Configured in `app/main.py` via `swagger_ui_init_oauth`. Requires:
- `CLERK_OAUTH_CLIENT_ID` and `CLERK_OAUTH_CLIENT_SECRET` from Clerk dashboard
- Redirect URI `http://localhost:8000/oauth2-redirect` registered in Clerk's OAuth app settings

## Environment Variables

| Variable | Description |
|----------|-------------|
| `CLERK_SECRET_KEY` | Clerk Backend API secret key |
| `CLERK_ISSUER` | Clerk instance URL (e.g., `https://your-instance.clerk.accounts.dev`) |
| `CLERK_OAUTH_CLIENT_ID` | OAuth app client ID (for Swagger UI) |
| `CLERK_OAUTH_CLIENT_SECRET` | OAuth app client secret (for Swagger UI) |
| `CLERK_AUTHORIZE_URL` | OAuth authorize endpoint |
| `CLERK_TOKEN_URL` | OAuth token endpoint |
