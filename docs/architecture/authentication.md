# Authentication — from sign-in to the user row

How a person proves who they are, and how the API comes to trust it: the portals, Clerk,
the token and the user row. Who may then do what is authorization, in
[`authorization.md`](./authorization.md). Each side's mechanics live next to its code —
the portals in [`web-app.md`](./web-app.md), the server in
[`server/docs/authentication.md`](../../server/docs/authentication.md), the dashboard in
[`setup/clerk.md`](../setup/clerk.md) — and this doc links rather than repeats them. It
describes the system as it stands and is kept current.

---

## 1. The model

**Clerk owns identity, sessions and organizations.** There is no login or register
endpoint and no stored credential: the platform never sees a password.

**Sign-in is Clerk's components, embedded in each portal's own routes** — the `(auth)`
route group of `web-app/apps/*/src/app/` — not Clerk's hosted pages.

**The platform's own record of a person is the `user` row.** Its `clerk_id` is the only
link to Clerk; everything else in the database points at the row's own `id`
([`../data-model/account.md`](../data-model/account.md)).

**Few places know Clerk.** On the web, only `@app/auth` reads its session
([`web-app.md`](./web-app.md) §4). On the server, `AuthMiddleware`, the `clerk`
integration, and `get_current_role()` — the one function that turns the token's role into
a `Role`, as `getUserRole()` does on the web. A change of provider rewrites those and no
route.

**Sign-up is open today.** Anyone can sign up on the internal portal and lands on
`/unauthorized` with no organization; the supplier portal has no sign-up page
([`../TODO.md`](../TODO.md), **Clerk — invitation-only sign-up**).

## 2. The token

**Every API call carries Clerk's session token** — a JWT signed by Clerk (RS256), sent as
`Authorization: Bearer <token>`. Not a cookie, and not a token of the platform's own: the
server issues nothing. The portals use Clerk's default session token — `getToken()` takes
no JWT template.

**It is short-lived.** It expires after 60 seconds, and Clerk's SDK refreshes it in the
background while the session lasts; `useApiFetch` asks for it on every call and gets the
current one. Signing out ends the session, and with it the refresh. The flip side: a claim
can be up to a minute stale after what it describes changes — a role, the active
organization.

**The server reads six claims.** PyJWT also checks `nbf` and `iat`; the rest Clerk adds
(`sid`, `jti`, `fva`, …) are ignored:

| Claim | Holds | Read by |
|---|---|---|
| `iss` | the Clerk instance that signed it | the verifier: must equal `CLERK_ISSUER` |
| `exp` | expiry | the verifier |
| `azp` | the origin that requested the token | the verifier: must be in `ALLOWED_ORIGINS` |
| `sub` | the user's Clerk id | `AuthMiddleware` → `clerk_id`, the key to the `user` row |
| `o.id` | the active organization's id | `AuthMiddleware` → `org_id` |
| `o.rol` | the user's role in it, e.g. `org:supplier` | `AuthMiddleware` → `org_role` |

**`o` is present only while an organization is active.** A signed-in person with none
selected — or partway through an invitation — sends a token without it; the server then
takes the org and role from Clerk's API ([`authorization.md`](./authorization.md) §2).

**Swagger sends a different token.** The `/docs` Authorize flow gets an OAuth access
token from Clerk: a JWT with `client_id` instead of `azp`, and no `o`.

## 3. One trip

```
portal (signed in)          @app/auth: useAppAuth().getToken() — fresh on every call
  → useApiFetch             Authorization: Bearer <session token>
  → AuthMiddleware          verify: RS256 against Clerk's JWKS, issuer = CLERK_ISSUER, exp
                            party: azp ∈ ALLOWED_ORIGINS, or client_id = CLERK_OAUTH_CLIENT_ID
                            reads sub → clerk_id, o.id → org_id, o.rol → org_role
  → CurrentUser             the user row, created on first sight (JIT)       401 if no valid token
```

`AuthMiddleware` verifies and never blocks. A route that needs a person declares
`CurrentUser`, and the decisions after that are authorization's
([`authorization.md`](./authorization.md) §2).

**The audience is not checked; the token's party is.** A portal's token must carry an
`azp` in `ALLOWED_ORIGINS`; Swagger's passes on `client_id` instead
(`server/app/utils/auth.py`). So `ALLOWED_ORIGINS` is part of authentication, not just
CORS: a portal origin missing from it is refused a valid token. Which origins to list is
[`setup/clerk.md`](../setup/clerk.md) §4.

## 4. The user row

**It is created by whichever lands first — `user.created`, `organizationMembership.created`, or JIT
on the first authenticated request.** For an invited person a webhook usually wins, and
the row exists before they ever sign in. JIT is the backstop: `UserService.resolve_user`
(`server/app/modules/account/service.py`) finds no row, asks Clerk's API, and creates it —
`org_id` from the token, or from Clerk's membership API when the token carries none. A
person with no organization membership at all gets a `403`.

**It is kept current by webhooks, not by signing in** — `user.created`, `user.updated`,
`user.deleted`, and `organizationMembership.created`, `.updated` and `.deleted`
([`setup/clerk-webhooks.md`](../setup/clerk-webhooks.md)).

| Field | Written by |
|---|---|
| `email`, `email_verified`, `first_name`, `last_name`, `avatar_url` | at creation (webhook or JIT); afterwards only the `user.*` webhooks, which skip an event older than `last_synced_at` |
| `org_id` | the token, on every request that carries one; the membership webhooks |
| the role | never stored — the token, else Clerk's API, cached 60 s ([`authorization.md`](./authorization.md) §2) |

**A missed webhook leaves the profile stale until the next `user.*` event.** A request
refreshes an existing row's `org_id` and nothing else.

**`user.deleted` runs the same erasure as `DELETE /api/v1/auth/me`.** The cascade is in
[`server/CLAUDE.md`](../../server/CLAUDE.md), **GDPR — Right to Erasure**.

## 5. Signing out

`signOut()` from `useAppAuth()` ends the Clerk session and then loads the sign-out URL as
a new document, so nothing the previous user cached survives in the browser. The
mechanism, and why `QueryProvider` sits in the signed-in layout, are
[`web-app.md`](./web-app.md) §4.

## 6. Where each step lives

| Step | Portal | Clerk | Server |
|---|---|---|---|
| Sign in | `(auth)` routes, Clerk's components | the session, the organization, the role | — |
| Reach a screen | `proxy.ts`: `auth.protect()`, then role → portal | — | — |
| Call the API | `useApiFetch`, a fresh token per call | issues the token | `AuthMiddleware` verifies it |
| Know the person | `useAppAuth().user` (`AppUser`) | the user | `CurrentUser`, the `user` row |
| Stay in sync | — | webhooks | `app/modules/account/webhooks.py` |
| Sign out | `signOut()`, then a new document | ends the session | — |
