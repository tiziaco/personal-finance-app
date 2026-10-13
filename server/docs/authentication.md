# Authentication System

## Overview

The server's side of authentication: verifying the token and provisioning the user. The end-to-end path — app, Clerk, token, user row — is
[`docs/architecture/authentication.md`](../../docs/architecture/authentication.md).

## Architecture

```
Request
  |
  v
AuthMiddleware              Extracts JWT, verifies via JWKS (RS256)
  |                         Stores clerk_id in request.state.clerk_id
  v
get_current_user (DI)       JIT provisioning: DB -> Clerk API
  |                         Stores internal user_id in request.state.user_id
  v
Route Handler               Receives User object via CurrentUser
```

## Dual ID System

| ID | Type | Purpose |
|----|------|---------|
| `id` | UUID string (PK) | Internal DB relationships, foreign keys |
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

### 3. Auth Dependencies — `app/modules/account/dependencies.py`

Two dependencies, used together:

- **`get_clerk_id(request)`** — reads `clerk_id` from `request.state`; raises `401` if absent
- **`get_current_user(clerk_id, session)`** — resolves `clerk_id` to a `User` object via JIT provisioning; sets `request.state.user_id` to the internal UUID

The type alias `CurrentUser = Annotated[User, Depends(get_current_user)]` is used in route signatures.

### 4. JIT User Provisioning — `app/modules/account/service.py`

`UserService.resolve_user(session, clerk_id)` follows this flow:

1. **DB lookup** — query by `clerk_id` (unique + indexed, so a single index scan)
2. **Clerk API** — fetch user from Clerk, create in DB, then publish `USER_SYNCED` (no subscribers yet)

Race condition handling: if two concurrent requests try to create the same user, the `IntegrityError` on the unique `clerk_id` constraint is caught, and the existing user is fetched instead.

There is deliberately **no `clerk_id -> user_id` cache**. A hit would still cost one indexed lookup, and FastAPI caches each `Depends` result per request (`use_cache=True` by default), so a single request never resolves the user twice anyway.

### 5. Clerk Client — `app/integrations/clerk/client.py`

`ClerkClient` wraps the `clerk-backend-api` SDK:
- `get_user(clerk_id)` — fetches user data from Clerk API
- `get_primary_email(clerk_user)` — extracts primary email from Clerk user object

Called via `asyncio.to_thread()` since the SDK is synchronous.

### 6. User Repository — `app/modules/account/repository.py`

`UserRepository` handles all user DB operations via SQLModel/SQLAlchemy:
- `get_by_id()`, `get_by_clerk_id()`
- `create()` and `create_or_get()` — create a user from Clerk data
- `update_from_clerk()` — syncs profile changes
- `delete()`

### 7. Caching

There is no in-memory cache in the auth path: the user lookup is one indexed query, and
there are no roles to cache.

## Swagger UI OAuth2

The `/docs` page has an "Authorize" button that triggers Clerk's OAuth2 Authorization Code flow. Configured in `app/main.py` via `swagger_ui_init_oauth`. Requires:
- `CLERK_OAUTH_CLIENT_ID` from Clerk dashboard (public client — no secret needed, uses PKCE)
- Redirect URI `http://localhost:8100/oauth2-redirect` registered in Clerk's OAuth app settings

## Environment Variables

| Variable | Description |
|----------|-------------|
| `CLERK_SECRET_KEY` | Clerk Backend API secret key |
| `CLERK_ISSUER` | Clerk instance URL (e.g., `https://your-instance.clerk.accounts.dev`) |
| `CLERK_OAUTH_CLIENT_ID` | OAuth app client ID (for Swagger UI) |
| `CLERK_AUTHORIZE_URL` | OAuth authorize endpoint |
| `CLERK_TOKEN_URL` | OAuth token endpoint |
