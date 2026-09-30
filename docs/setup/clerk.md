# Clerk — Setup Procedure

Everything you must do **in the Clerk dashboard** before this stack authenticates
anyone, plus the environment variables each step produces.

Do this first. Then [`clerk-webhooks.md`](./clerk-webhooks.md) for event delivery.
For how the code consumes the token once it arrives, see
[`../architecture/authentication.md`](../architecture/authentication.md).

Clerk is the only identity provider wired in, and it supplies **both** authentication
and multi-tenancy — the tenant is a Clerk Organization. There is no local password
store and no login endpoint to build.

---

## What you are creating

| In Clerk | Produces | Consumed by |
|---|---|---|
| An application | publishable + secret key | both portals, the server |
| Organizations, enabled | `org_id` on every session token | tenant scoping in every query |
| Four organization roles | `org_role` on the token | `Role` enum, `require_role()`, `<Protect>` |
| (optional) An OAuth app | `CLERK_OAUTH_CLIENT_ID` | the Authorize button on `/docs` |
| A webhook endpoint | `CLERK_WEBHOOK_SIGNING_SECRET` | see `clerk-webhooks.md` |

---

## 1. Enable Organizations

**Dashboard → Organizations → enable.**

Multi-tenancy in this template *is* Clerk Organizations. The org id arrives on the JWT
and scopes DB queries; nothing else establishes the tenant.

A signed-in user with no **active** organization gets `org_id = None`
(`server/app/api/middlewares/auth.py`). They are authenticated but belong to no tenant,
so tenant-scoped queries return nothing. That looks like an empty database, not an auth
problem — see the symptom table at the end.

Each user must therefore be a member of an organization, with one selected as active.
Neither portal has an organization switcher, so the active one comes from Clerk at
sign-in: **turn personal accounts off** (Dashboard → Organizations), or a member can sign
in with none active and has no way to fix it.

---

## 2. Create the four organization roles

**Dashboard → Organizations → Roles.** Create these four, with these exact slugs:

| Slug (create this) | On the token as | Portal |
|---|---|---|
| `project_manager` | `org:project_manager` | internal |
| `reviewer` | `org:reviewer` | internal |
| `approver` | `org:approver` | internal |
| `supplier` | `org:supplier` | external |

**Clerk's built-in roles are not app roles.** `org:admin` (an organization's creator) and
`org:member` (Clerk's default for new members) are rejected by both portals and the API:
assign every member one of the four, and make one of them the default role for new members.

**The `org:` prefix is Clerk's, not yours.** You create `project_manager`; Clerk emits
`org:project_manager`; `getUserRole()` strips the prefix
(`web-app/packages/auth/src/permissions.ts`). That is why the two layers look
inconsistent and are not:

```tsx
<Protect role="org:project_manager">   // Clerk's own gate — prefixed
role === Role.PROJECT_MANAGER          // our code — stripped
```

A slug typo does not raise anything. `getUserRole()` returns `null` for an unrecognised
value, `isInternalRole(null)` is `false`, and the user is redirected to `/unauthorized` on
every route — which reads like a real permissions problem, not the slug typo that caused
it.

These four are the **example domain's** roles. Renaming them is a code change *and* a
dashboard change; see [`making-it-yours.md`](./making-it-yours.md). What each is for is
in [`../product/features/account.md`](../product/features/account.md) §3.

---

## 3. Keys

**Dashboard → API keys.**

Server — `server/.env.<environment>`:

| Variable | Value |
|---|---|
| `CLERK_SECRET_KEY` | `sk_test_…` / `sk_live_…` |
| `CLERK_ISSUER` | your instance URL, e.g. `https://your-app.clerk.accounts.dev` |

`CLERK_ISSUER` is the trust anchor, not a display setting: the JWKS URL used to verify
every RS256 signature is derived from it (`AuthSettings.jwks_url`).

Both portals — `web-app/apps/<portal>/.env.local`:

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | `pk_test_…` / `pk_live_…` |
| `CLERK_SECRET_KEY` | same secret key |
| `NEXT_PUBLIC_CLERK_SIGN_IN_URL` | `/sign-in` |
| `NEXT_PUBLIC_CLERK_SIGN_UP_URL` | `/sign-up` |
| `NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL` | `/home` |
| `NEXT_PUBLIC_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL` | `/home` |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8100` in dev |

None of these are read by application code. The Clerk SDK picks them up from the
environment itself — `mergeNextClerkPropsWithEnv` in `@clerk/nextjs` maps each one onto
a `<ClerkProvider>` prop — which is why grepping the repo for them finds only config
files and docs.

`FALLBACK`, not `FORCE`, and not the older `AFTER_SIGN_IN_URL`: the legacy names
map onto props `@clerk/nextjs` v6 deprecated, and a sign-in reached with a
`?redirect_url=` ignores the legacy prop outright rather than falling back to it.
The fallback form honours the requested destination and only defaults to `/home`
when none was asked for.

> **The `NEXT_PUBLIC_*` values are baked in at image build time**, not read at runtime —
> Next.js inlines them, so changing one means rebuilding. Today both portal images are
> built with the internal portal's values; why, and when that stops being harmless:
> [`deploy-dokploy.md`](./deploy-dokploy.md).

---

## 4. `ALLOWED_ORIGINS` — the setting that fails like a bug

In `server/.env.<environment>`. It gates **two** things, which is why a missing entry is
so confusing:

1. **CORS** (`app/api/middlewares/cors.py`) — the browser calls the API cross-origin;
   there is no server-side proxy hop.
2. **The Clerk `azp` token-party check** (`app/utils/auth.py`). A session token carries
   `azp` = the origin that requested it. If that origin is not listed, the token is
   rejected as `token_party_not_allowed` — **a valid, unexpired, correctly-signed token
   is refused.**

So every portal origin must be listed, per environment:

```bash
# JSON array — see the warning below
ALLOWED_ORIGINS=["http://localhost:3000","http://localhost:3002"]
```

> **It must be a JSON array.** `ALLOWED_ORIGINS` is a `List[str]`, and pydantic-settings
> parses complex types as JSON. A comma-separated value does not degrade — the server
> refuses to start with
> `SettingsError: error parsing value for field "ALLOWED_ORIGINS"`.

In staging and production list the real portal hostnames. Miss one and that portal's
users get 401s from an API that is working perfectly.

---

## 5. Swagger's Authorize button (optional)

Only needed if you want to call authenticated endpoints from `/docs`.

**Dashboard → OAuth applications → create a public client** (PKCE, no secret), and
register the redirect URI `http://localhost:8100/oauth2-redirect`.

```bash
CLERK_OAUTH_CLIENT_ID=...
CLERK_AUTHORIZE_URL=...
CLERK_TOKEN_URL=...
```

OAuth access tokens carry no `azp` at all — they are authorised by `client_id` matching
`CLERK_OAUTH_CLIENT_ID` instead, which is why `/docs` works without its own origin in
`ALLOWED_ORIGINS`.

---

## 6. Webhooks

User and membership events (JIT provisioning, role changes, offboarding) arrive by
webhook. Full procedure, including the ngrok tunnel for local delivery:
[`clerk-webhooks.md`](./clerk-webhooks.md).

---

## Symptom → cause

| What you see | Likely cause |
|---|---|
| Signed in, but every route bounces you back | Role slug mismatch — `getUserRole()` returned `null`. Check §2 spelling, and that the member holds one of the four roles, not Clerk's default `org:admin` / `org:member`. |
| 401 from the API, token looks valid | The portal's origin is missing from `ALLOWED_ORIGINS` (§4). Server log: `token_party_not_allowed`. |
| Server won't start, `SettingsError` on `ALLOWED_ORIGINS` | Not a JSON array (§4). |
| Signed in, everything empty, no errors | No **active** organization → `org_id = None` (§1). |
| 403 `SUPPLIER_NOT_LINKED` | A `supplier`-role user with no `Supplier.contact_id` pointing at them. Expected until the invitation carrying `supplier_id` metadata is accepted. |
| Browser CORS error on every request | Same as the 401 row — one setting, two symptoms (§4). |
| Roles work locally, not in staging/production | `ALLOWED_ORIGINS` is per-environment; each `server/.env.<env>` needs its own origins. |
| Role change in Clerk not taking effect | Cached 60s, invalidated by membership webhooks. If webhooks aren't delivering, it degrades to the TTL — see `clerk-webhooks.md`. |
