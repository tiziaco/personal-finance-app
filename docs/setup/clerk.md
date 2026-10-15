# Clerk — Setup

Clerk supplies authentication; the user is the tenant, so there are no organisations and no
roles to configure. How the code consumes the token:
[`../architecture/authentication.md`](../architecture/authentication.md).

Most of the setup is scripted, against a **development** instance. With the
[Clerk CLI](https://clerk.com/docs/cli) and `jq` installed (`brew install clerk/stable/clerk
jq`), and `clerk auth login` done once, `make clerk-setup` runs the first three of these in
order. Re-running it is safe: it skips creating the app once `CLERK_APP_ID` is set.

```bash
make clerk-bootstrap-env    # create the app; its keys into the env files (§3)
make clerk-apply-config     # scripts/clerk/config.json → the instance (§1)
make clerk-seed-users       # the two dev users (§2)
make clerk-check-config     # fail if the instance has drifted from config.json
make clerk-pull-config      # refresh config.json from the instance
make clerk-bootstrap-oauth  # optional — Swagger's Authorize button (§5)
```

`clerk-setup` is `clerk-bootstrap-env` (skipped when `CLERK_APP_ID` is set), then
`clerk-apply-config`, then `clerk-seed-users`.

What they do not do: `ALLOWED_ORIGINS` (§4), a decision about your own deployment; the
webhook endpoint (§6), which no Clerk API creates; and the Account Portal sign-up toggle
(§7). Every script refuses anything but a development instance; production is by hand (§8).

## Team setup

Each developer runs the sequence against **their own** Clerk application, with their own
ngrok domain and webhook endpoint:

```bash
make clerk-setup CLERK_APP_NAME="Personal Finance Dev — <name>"
```

`CLERK_APP_ID` lives in the gitignored root `.env`, so nothing is shared. Not one shared
dev instance: Clerk delivers every event to every endpoint, so each developer's database
would receive everyone else's users and deletions. Creating an application needs that
permission in the team's Clerk workspace.

Local webhooks are needed only for work on the handlers. Without the tunnel, sign-in still
works — JIT provisioning creates the user on first request — and what is lost is profile
edits made in Clerk and account deletion made there (from Clerk's profile window or the
dashboard). Staging and production are each one
shared instance with one endpoint at the real API URL.

## Reusing an existing instance

To point this repo at a Clerk application that already exists, skip `clerk-bootstrap-env`:

1. Set `CLERK_APP_ID` in the root `.env`, and put the instance's keys in the env files (§3).
2. `make clerk-pull-config`, then review `git diff scripts/clerk/config.json`. Applying
   writes the file's values to the instance, so a difference is a setting the apply will
   change.
3. Keep every setting the app depends on in `config.json`; settings that live only in the
   dashboard are what `make clerk-check-config` cannot see. Then `make clerk-setup`, which
   skips creating the app and applies the config and the dev users.

---

## 1. Instance settings

```bash
make clerk-apply-config   # scripts/clerk/config.json → the instance
make clerk-check-config   # fail if the instance has drifted from the file
make clerk-pull-config    # the other direction: instance → the file
```

[`scripts/clerk/config.json`](../../scripts/clerk/config.json) is the committed copy of every
instance setting the app depends on:

- **Organizations off** (`organization_settings.enabled: false`). The user is the tenant;
  a token carries no `o` claim, and one that does is ignored.
- **Sign-up public** (`sign_up_mode: public`) (§7).
- **Email and password**, with the email-code verification and sign-in strategy; first and
  last name enabled and optional.
- **Password sign-in without the device-trust challenge, and Have I Been Pwned off at
  sign-in** (`enforce_hibp_on_sign_in: false`) — what lets a seeded user with a throwaway
  password sign in at all. The breach check stays on at sign-up.

`make clerk-check-config` re-pulls the instance and diffs it against the committed file;
its failure message says how to keep either side.

---

## 2. Dev users

```bash
make clerk-seed-users
```

Creates the users in
[`server/data/clerk-dev-seed.json`](../../server/data/clerk-dev-seed.json) — committed on
purpose: fake emails, throwaway passwords, and a script that refuses anything but a
development instance.

| User | Purpose |
|---|---|
| `dev-alice@example.com` | the first user |
| `dev-bob@example.com` | the second, to check isolation |

Sign in on the app (`:3000`); the passwords are in the file. Re-running is a no-op.

**The isolation check.** Sign in as Alice, create a conversation and note its id; sign in as
Bob and request that id. The answer is a 404 `CONVERSATION_NOT_FOUND`, the same as for an
id that does not exist, and Bob's conversation list does not include it.

---

## 3. Keys

`make clerk-bootstrap-env` creates the application and writes its keys:

| File | Variables |
|---|---|
| root `.env` | `CLERK_APP_ID` — read by every other `clerk-*` target |
| `server/.env.development` | `CLERK_SECRET_KEY`, `CLERK_ISSUER` |
| `web-app/apps/web/.env.local` | `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY` |

It refuses to run while `CLERK_APP_ID` is set: it creates a new application. Restart the dev
servers afterwards — none re-reads its env file. `CLERK_ISSUER` is the trust anchor: the
JWKS URL that verifies every token is derived from it (`AuthSettings.jwks_url`). By hand,
all three values are on **Dashboard → API keys**; the issuer is the Frontend API URL.

> **`NEXT_PUBLIC_*` values are baked in at image build time.** Changing one means
> rebuilding the image ([`deploy-dokploy.md`](./deploy-dokploy.md)).

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

So the web origin must be listed, per environment:

```bash
# JSON array — see the warning below
ALLOWED_ORIGINS=["http://localhost:3000","http://localhost:8100"]
```

> **It must be a JSON array.** `ALLOWED_ORIGINS` is a `List[str]`, and pydantic-settings
> parses complex types as JSON. A comma-separated value does not degrade — the server
> refuses to start with
> `SettingsError: error parsing value for field "ALLOWED_ORIGINS"`.

In staging and production list the real web hostname. Miss it and the app's users get 401s
from an API that is working perfectly.

---

## 5. Swagger's Authorize button (optional)

```bash
make clerk-bootstrap-oauth
```

Registers a public PKCE OAuth application, or reuses the one already registered, and
writes `CLERK_OAUTH_CLIENT_ID`, `CLERK_AUTHORIZE_URL` and `CLERK_TOKEN_URL` to
`server/.env.development`; restart the API. Its scopes and redirect URI match
`server/app/main.py`; the URI is `http://localhost:$API_HOST_PORT/oauth2-redirect` —
`http://localhost:8100/oauth2-redirect` by default (override: `CLERK_OAUTH_REDIRECT_URI`), and
a re-run from a checkout on another port adds that port's URI to the same client. OAuth
access tokens carry no `azp` and are authorised by `client_id` instead — which is why
`/docs` needs no entry in `ALLOWED_ORIGINS`.

---

## 6. Webhooks

User events — creation, profile edits, deletion — reach the server at
`POST /api/v1/webhooks/clerk`. Sign-in does not need them to *start*: JIT provisioning
creates the user on first request. But the webhook is what keeps the app's rows in step with
Clerk. Without it, a deleted or changed account leaves a stale row behind. That row does not
lock anyone out: email is not unique, because Clerk owns it and `clerk_id` is the identity
([`data-model/account.md`](../data-model/account.md), D3). **This is the one step with no script** — no
Clerk API creates an endpoint or returns its signing secret.

### ngrok (development, once per developer)

1. In the ngrok dashboard, claim the free static domain (**Domains**) and copy the
   authtoken (**Your Authtoken** — about 49 characters, no prefix; `rd_…`, `cr_…` and
   `ak_…` are resource ids and do not authenticate). The workspace picker must be on the
   workspace that owns the domain.
2. Add both to the root `.env`:

   ```env
   NGROK_DOMAIN=dapper-cat-1234.ngrok-free.app
   NGROK_AUTHTOKEN=2abc...
   ```

3. `make dev-tunnel` on the native path; the compose `ngrok` service on the Docker path.

A host ngrok install's config file (`~/Library/Application Support/ngrok/ngrok.yml`) wins
over `NGROK_AUTHTOKEN`, and a stale token there fails with `ERR_NGROK_320`. Both paths
avoid it: `make dev-tunnel` passes `--authtoken`, and the compose service has no config
file.

### The endpoint

In the Clerk dashboard, **check the instance switcher first** — an endpoint on the wrong
instance means no event ever arrives. Then **Webhooks → Add Endpoint**:

| Instance | Endpoint URL |
|---|---|
| Development | `https://<NGROK_DOMAIN>/api/v1/webhooks/clerk` |
| Production | `https://<your-api-domain>/api/v1/webhooks/clerk` |

Subscribe to exactly three events, picked from the catalog: `user.created`, `user.updated`
and `user.deleted`. Anything else is logged and discarded.

### The signing secret

Each endpoint has its own `whsec_…`, on the endpoint's settings page — not on the API keys
page, and it does not exist before the endpoint does.

| Environment | `CLERK_WEBHOOK_SIGNING_SECRET` goes in |
|---|---|
| Development | `server/.env.development` |
| Production | the platform's secret store, never a file in the image |
| Tests | `server/.env.test` — any valid `whsec_<base64>`; svix decodes it, so `whsec_dummy` fails |

Development and production secrets differ. A dev secret in production 401s every event,
and signature failures all look alike in the logs — check the secret first.

**Verify:** the endpoint's **Testing** tab → send `user.created` → Clerk logs **204** and the
server logs the event type. **Rotate:** rolling the secret takes effect at once, with no
grace period — update the environment and restart in the same window.

---

## 7. Public sign-up

`sign_up_mode` is `public`: anyone can create an account. The app serves the pages itself, at
`/sign-in` and `/sign-up` (Clerk's components, in the `(auth)` route group), and a new user's
first authenticated request provisions their row — no invitation, organisation or role is
involved.

The Account Portal is Clerk's hosted fallback and has its own sign-up toggle that
`config.json` does not hold. Once per app, in the dashboard, check **Account Portal →
Sign-up** is enabled, so a link to Clerk's hosted pages does not dead-end.

---

## 8. Production instance

The scripts refuse anything but a development instance, so production is configured by
hand, from the same file:

1. **Settings** — everything in `scripts/clerk/config.json` except what exists only for
   seeded users: keep Have I Been Pwned on (`disable_hibp`, `enforce_hibp_on_sign_in`).
2. **Keys** (§3) into the platform's environment, `ALLOWED_ORIGINS` with the real web
   hostname (§4), and the webhook endpoint with its secret (§6).
3. **Account Portal → Sign-up** enabled (§7).

---

## Symptom → cause

| What you see | Likely cause |
|---|---|
| You sign in, land on the dashboard, get a "session expired" toast and are sent back to `/sign-in`, every time (the server log shows 401 from the API) | The web origin is missing from `ALLOWED_ORIGINS` (§4). Server log: `token_party_not_allowed`. |
| Every request fails with 503 `AUTH_UNAVAILABLE`, and you are not signed out | The server cannot reach Clerk's JWKS endpoint (a network problem, or a wrong `CLERK_ISSUER` in the server env). Server log: `token_jwks_unreachable`. |
| Server won't start, `SettingsError` on `ALLOWED_ORIGINS` | Not a JSON array (§4). |
| Browser CORS error on every request | Same as the 401 row — one setting, two symptoms (§4). |
| Works locally, not in staging/production | `ALLOWED_ORIGINS` is per-environment; each `server/.env.<env>` needs its own origins. |
| A new user signs up and the first call answers 503 `USER_PROVISIONING_FAILED` "Failed to provision user" | Clerk's API was unreachable or the user has no primary email — see the `user_provisioning_failed` log line. |
| Every webhook delivery 401s | Wrong `whsec_` for this instance, or the variable never reached the process — check the running process's environment, not the file (§6). |
| No webhook deliveries at all | Endpoint on the wrong instance, or the tunnel is down (§6). |
| ngrok `ERR_NGROK_320` | The authtoken belongs to a different account than the domain — check the host `ngrok.yml`, which beats the env var (§6). |
| ngrok `ERR_NGROK_105` | A resource id (`rd_`, `cr_`, `ak_`) pasted instead of the authtoken (§6). |
| Webhook deliveries 404 | The path is `/api/v1/webhooks/clerk` (§6). |
| Container exits at startup naming `CLERK_WEBHOOK_SIGNING_SECRET` | `REQUIRED_ENV_VARS` in `server/scripts/docker-entrypoint.sh` — set the secret. |
| Deliveries succeed, database unchanged | Not setup — look for `webhook_event_stale` or a missing-row warning in the handler logs. |
| `make clerk-check-config` fails | The instance was changed in the dashboard; the message says how to keep either side. |
| Sign-in fails for a seeded user with the right password | `make clerk-apply-config` was not run — password sign-in or the HIBP relaxation is missing (§1). |
