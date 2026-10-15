# Authentication — from sign-in to the user row

How a person proves who they are, and how the API comes to trust it: the app, Clerk,
the token and the user row. Who may then do what is authorization, in
[`authorization.md`](./authorization.md). Each side's mechanics live next to its code —
the app in [`web-app.md`](./web-app.md), the server in
[`server/docs/authentication.md`](../../server/docs/authentication.md), the dashboard in
[`setup/clerk.md`](../setup/clerk.md) — and this doc links rather than repeats them. It
describes the system as it stands and is kept current.

---

## 1. The model

**Clerk owns identity and sessions.** There is no login or register
endpoint and no stored credential: the platform never sees a password.

**Sign-in and sign-up are Clerk's components, embedded in the app's own routes** —
`/sign-in` and `/sign-up`, in the `(auth)` route group of `web-app/apps/web/src/app/` — not
Clerk's hosted pages.

**The platform's own record of a person is the `user` row.** Its `clerk_id` is the only
link to Clerk; everything else in the database points at the row's own `id`
([`../data-model/account.md`](../data-model/account.md)).

**Few places know Clerk.** On the web, only `@app/auth` reads its session
([`web-app.md`](./web-app.md) §4). On the server, `AuthMiddleware` and the `clerk`
integration. A change of provider rewrites those and no route.

**Sign-up is public.** The instance runs `sign_up_mode: public`: anyone may create an
account at `/sign-up`, and the first authenticated request provisions their row
([`../setup/clerk.md`](../setup/clerk.md) §7).

## 2. The token

**Every API call carries Clerk's session token** — a JWT signed by Clerk (RS256), sent as
`Authorization: Bearer <token>`. Not a cookie, and not a token of the platform's own: the
server issues nothing. The app uses Clerk's default session token — `getToken()` takes
no JWT template.

**It is short-lived.** It expires after 60 seconds, and Clerk's SDK refreshes it in the
background while the session lasts; `useApiFetch` asks for it on every call and gets the
current one. Signing out ends the session, and with it the refresh. The flip side: a claim
can be up to a minute stale after what it describes changes.

**Straight after sign-in, it is waited for.** Clerk navigates to the redirect before the
new session is installed, so the first render's requests find no session and Clerk's
`getToken()` answers `null`. `@app/auth`'s `getToken` waits for the session instead, up
to five seconds, and the first queries go out with a token.

**The server reads four claims.** PyJWT also checks `nbf` and `iat`; the rest Clerk adds
(`sid`, `jti`, `fva`, …) are ignored:

| Claim | Holds | Read by |
|---|---|---|
| `iss` | the Clerk instance that signed it | the verifier: must equal `CLERK_ISSUER` |
| `exp` | expiry | the verifier |
| `azp` | the origin that requested the token | the verifier: must be in `ALLOWED_ORIGINS` |
| `sub` | the user's Clerk id | `AuthMiddleware` → `clerk_id`, the key to the `user` row |

**Any other claim is ignored.** A token that still carries an `o` claim — from a stale
session or a Clerk default — puts nothing on `request.state`.

**Swagger sends a different token.** The `/docs` Authorize flow gets an OAuth access
token from Clerk: a JWT with `client_id` instead of `azp`.

## 3. One trip

```
app (signed in)             @app/auth: useAppAuth().getToken() — fresh on every call
  → useApiFetch             Authorization: Bearer <session token>
  → AuthMiddleware          verify: RS256 against Clerk's JWKS, issuer = CLERK_ISSUER, exp
                            party: azp ∈ ALLOWED_ORIGINS, or client_id = CLERK_OAUTH_CLIENT_ID
                            reads sub → clerk_id
  → CurrentUser             the user row, created on first sight (JIT)       401 if no valid token
```

`AuthMiddleware` verifies and never blocks. A route that needs a person declares
`CurrentUser`, and the decisions after that are authorization's
([`authorization.md`](./authorization.md) §2).

**A 401 ends the session on the web.** The web retries it once with a fresh token, then
signs out. So the server answers 401 only when the request's credentials fail; an outage
behind valid ones is a 5xx ([`server.md`](./server.md)).

**The audience is not checked; the token's party is.** The app's token must carry an
`azp` in `ALLOWED_ORIGINS`; Swagger's passes on `client_id` instead
(`server/app/utils/auth.py`). So `ALLOWED_ORIGINS` is part of authentication, not just
CORS: the web origin missing from it is refused a valid token. Which origins to list is
[`setup/clerk.md`](../setup/clerk.md) §4.

## 4. The user row

**It is created by whichever lands first — the `user.created` webhook, or JIT on the first
authenticated request.** JIT is the backstop: `UserService.resolve_user`
(`server/app/modules/account/service.py`) finds no row, asks Clerk's API for the profile,
and creates it. A new user needs no organisation, role or invitation: the first request
returns 200. Both paths publish `USER_SYNCED`, which has no subscribers yet
([`server.md`](./server.md) §8).

**It is kept current by webhooks, not by signing in** — `user.created`, `user.updated` and
`user.deleted`, the only events the endpoint subscribes to
([`setup/clerk.md`](../setup/clerk.md) §6).

| Field | Written by |
|---|---|
| `email`, `email_verified`, `first_name`, `last_name`, `avatar_url` | at creation (webhook or JIT); afterwards only the `user.updated` webhook, which skips an event older than `last_synced_at` |

**A missed webhook leaves the profile stale until the next `user.updated` event.** A
request never refreshes an existing row.

**`user.deleted` runs the same erasure as `DELETE /api/v1/auth/me`.** The cascade is in
[`server/CLAUDE.md`](../../server/CLAUDE.md), **GDPR — Right to Erasure**.

## 5. Signing out

`signOut()` from `useAppAuth()` ends the Clerk session and then loads the sign-out URL as
a new document, so nothing the previous user cached survives in the browser. The
mechanism, and why `QueryProvider` sits in the signed-in layout, are
[`web-app.md`](./web-app.md) §4.

## 6. Where each step lives

| Step | App | Clerk | Server |
|---|---|---|---|
| Sign in or up | `/sign-in`, `/sign-up`, Clerk's components | the session | — |
| Reach a screen | `proxy.ts`: `auth.protect()` | — | — |
| Call the API | `useApiFetch`, a fresh token per call | issues the token | `AuthMiddleware` verifies it |
| Know the person | `useAppAuth().user` (`AppUser`) | the user | `CurrentUser`, the `user` row |
| Stay in sync | — | webhooks | `app/modules/account/webhooks.py` |
| Sign out | `signOut()`, then a new document | ends the session | — |
