# Clerk — Setup

Clerk supplies both authentication and multi-tenancy: the tenant is a Clerk Organization,
and the member's role in it arrives on the token. How the code consumes the token:
[`../architecture/authentication.md`](../architecture/authentication.md).

Most of the setup is scripted, against a **development** instance. With the
[Clerk CLI](https://clerk.com/docs/cli) and `jq` installed (`brew install clerk/stable/clerk
jq`), and `clerk auth login` done once, `make clerk-setup` runs the first four of these in
order. Re-running it is safe: it skips the first, which refuses once `CLERK_APP_ID` is set.

```bash
make clerk-bootstrap-env    # create the app; its keys into the env files (§3)
make clerk-apply-config     # instance and organization settings (§1)
make clerk-apply-roles      # the four roles, creator and default role (§1)
make clerk-seed-users       # a dev org and three internal users (§2)
make clerk-bootstrap-oauth  # optional — Swagger's Authorize button (§5)
```

What they do not do: `ALLOWED_ORIGINS` (§4), a decision about your own deployment; the
webhook endpoint (§6), which no Clerk API creates; and two dashboard toggles no
configuration key holds — user-created organizations off (§1) and the Account Portal
redirects (§7). Every script refuses anything but a development instance; production is by
hand (§8).

## Team setup

Each developer runs the sequence against **their own** Clerk application, with their own
ngrok domain and webhook endpoint:

```bash
make clerk-setup CLERK_APP_NAME="Template App Dev — <name>"
```

`CLERK_APP_ID` lives in the gitignored root `.env`, so nothing is shared. Not one shared
dev instance: Clerk delivers every event to every endpoint, so each developer's database
would receive everyone else's users and deletions. Creating an application needs that
permission in the team's Clerk workspace.

Local webhooks are needed only for work on the handlers. Without the tunnel, sign-in still
works — JIT provisioning creates the user and org on first request — and what is lost is
profile edits made in Clerk, offboarding, and instant role-change invalidation (the 60 s
cache still expires). Staging and production are each one shared instance with one
endpoint at the real API URL.

---

## 1. Instance, organizations and roles

```bash
make clerk-apply-config   # scripts/clerk/config.json → the instance
make clerk-apply-roles    # its x_organization_roles → roles, role set, creator and default role
make clerk-check-config   # fail if the instance has drifted from the file
```

[`scripts/clerk/config.json`](../../scripts/clerk/config.json) is the committed copy of every
instance setting the app depends on:

- **Organizations on, personal accounts off** (`force_organization_selection`). Neither
  portal has an organization switcher, so the active org has to come from Clerk at sign-in.
- **Sign-up restricted** to invitations (§7).
- **Password sign-in without the device-trust challenge, and Have I Been Pwned off at
  sign-in** — what lets a seeded user with a throwaway password sign in at all.
- **Organization deletion off in Clerk's UI** (`admin_delete_enabled: false`). No webhook
  handles `organization.deleted`, so a deletion from the UI would orphan the org's data.
  Deleting an org is an operator action.
- **Users cannot create organizations.** Tenants are created by `make clerk-seed-users` or
  in the dashboard. Otherwise a user left with no membership — removed, or a PM who left —
  is offered "Setup your organization" at sign-in and becomes the PM of a tenant of their
  own. Clerk's config has no key for it, so once per app, in the dashboard:
  **Organizations → Settings → Allow user-created organizations** off. That is the
  default for new users; the seeded users carry `create_organization_enabled: false`
  themselves (§2). Neither blocks the Backend API.
- **The roles**, under `x_organization_roles` — a key Clerk never uses, which
  `apply-config` strips and `apply-roles` applies.

| Slug | On the token as | Portal | System permissions |
|---|---|---|---|
| `project_manager` | `org:project_manager` | internal | read and manage members; manage and delete the org profile |
| `reviewer` | `org:reviewer` | internal | — |
| `approver` | `org:approver` | internal | — |
| `supplier` | `org:supplier` | supplier | — |

- **Creator role `project_manager`.** Whoever is set as an org's creator becomes its PM.
  Clerk accepts a creator role only if it can manage and read members and delete the
  organization — hence the delete permission, which the setting above keeps out of reach.
- **Default role `supplier`** — the role an invitation form starts on. An internal
  colleague invited with it by mistake lands on `/unauthorized`, not on internal data.
- **`org:admin` and `org:member` are deleted.** Both portals and the API reject them.

Two failures that do not look like configuration:

- **A slug typo sends everyone to `/unauthorized`.** Clerk emits `org:project_manager`;
  `getUserRole()` (`web-app/packages/auth/src/permissions.ts`) strips the prefix and returns
  `null` for anything it does not recognise. `<Protect role="org:project_manager">` is
  Clerk's gate and takes the prefix; `role === Role.PROJECT_MANAGER` is ours and does not.
- **No active organization reads as an empty database.** The token then has no `o` claim,
  `org_id` is `None` (`server/app/api/middlewares/auth.py`), and every tenant-scoped query
  returns nothing.

`make clerk-check-config` re-pulls the instance, roles included, and diffs it against the
committed file; its failure message says how to keep either side. Renaming a role: change
its key in `x_organization_roles` and in
[`server/data/clerk-dev-seed.json`](../../server/data/clerk-dev-seed.json), run
`make clerk-apply-roles` and `make clerk-seed-users`, then the code
([`making-it-yours.md`](./making-it-yours.md) §4). A new key is a new role: members holding
the old one land on `/unauthorized` until moved, and it is deleted only once no member or
invitation holds it — then re-run `make clerk-apply-roles` to delete it.

---

## 2. Dev users

```bash
make clerk-seed-users
```

Creates the organization and users in
[`server/data/clerk-dev-seed.json`](../../server/data/clerk-dev-seed.json) — committed on
purpose: fake emails, throwaway passwords, and a script that refuses anything but a
development instance.

| User | Role |
|---|---|
| `dev-pm@example.com` | `project_manager` — the org's creator |
| `dev-reviewer@example.com` | `reviewer` |
| `dev-approver@example.com` | `approver` |

Sign in on the internal portal (`:3000`); the passwords are in the file. With a single
membership Clerk activates the org at sign-in and lands on `/home`. None of them may create an
organization (§1). Re-running is a no-op; a role changed in the file is applied to the
membership. There is no seeded supplier
([`../TODO.md`](../TODO.md), **Clerk — supplier dev seed**).

---

## 3. Keys

`make clerk-bootstrap-env` creates the application and writes its keys:

| File | Variables |
|---|---|
| root `.env` | `CLERK_APP_ID` — read by every other `clerk-*` target |
| `server/.env.development` | `CLERK_SECRET_KEY`, `CLERK_ISSUER` |
| `web-app/apps/<portal>/.env.local`, both portals | `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY` |

It refuses to run while `CLERK_APP_ID` is set: it creates a new application. Restart the dev
servers afterwards — none re-reads its env file. `CLERK_ISSUER` is the trust anchor: the
JWKS URL that verifies every token is derived from it (`AuthSettings.jwks_url`). By hand,
all three values are on **Dashboard → API keys**; the issuer is the Frontend API URL.

> **`NEXT_PUBLIC_*` values are baked in at image build time.** Changing one means
> rebuilding. Both portal images are built with the internal portal's values today — why,
> and when that stops being harmless: [`deploy-dokploy.md`](./deploy-dokploy.md).

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

```bash
make clerk-bootstrap-oauth
```

Registers a public PKCE OAuth application and writes `CLERK_OAUTH_CLIENT_ID`,
`CLERK_AUTHORIZE_URL` and `CLERK_TOKEN_URL` to `server/.env.development`; restart the API.
Its scopes and redirect URI match `server/app/main.py`; the URI is
`http://localhost:$API_HOST_PORT/oauth2-redirect` (override: `CLERK_OAUTH_REDIRECT_URI`), and
a re-run from a checkout on another port adds that port's URI to the same client. OAuth
access tokens carry no `azp` and are authorised by `client_id` instead — which is why
`/docs` needs no entry in `ALLOWED_ORIGINS`.

---

## 6. Webhooks

User and membership events — profile edits, offboarding, role changes — reach the server
at `POST /api/v1/webhooks/clerk`. Sign-in does not depend on them: JIT provisioning
creates the user and org on first request. **This is the one step with no script** — no
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

Subscribe to exactly six events, picked from the catalog: `user.created`, `user.updated`,
`user.deleted`, `organizationMembership.created`, `organizationMembership.updated`,
`organizationMembership.deleted`. Anything else is logged and discarded.

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

## 7. Sign-up is invitation-only

`sign_up_mode` is `restricted`: nobody signs up without an invitation. A project manager
invites from the organization profile in the internal portal, choosing a role; the
invitation email links to Clerk's hosted Account Portal, where the invitee creates their
account, then signs in on their role's portal. Neither portal has a sign-up page. Keeping
invitees on the portal's own domain: [`../TODO.md`](../TODO.md), **Clerk — ticket-aware
sign-up pages**.

The invitation link never passes through a portal, so the Account Portal gets no
`redirect_url`, and a portal's `NEXT_PUBLIC_CLERK_SIGN_UP_*_REDIRECT_URL` is never read.
Where the invitee lands after setting a password is the Account Portal's own fallback,
which `clerk config` cannot set. Once per app, in the dashboard: **Account Portal →
Redirects** → after sign-up and after sign-in fallbacks to
`http://localhost:$INTERNAL_PORTAL_HOST_PORT/home`. Unset, the invitee stays on Clerk's
page and has to sign in on the portal themselves.

---

## 8. Production instance

The scripts refuse anything but a development instance, so production is configured by
hand, from the same file:

1. **Settings** — everything in `scripts/clerk/config.json` except what exists only for
   seeded users: keep Have I Been Pwned on (`disable_hibp`, `enforce_hibp_on_sign_in`).
2. **Roles & Permissions** — the four roles and permissions in `x_organization_roles`;
   `project_manager` as creator role, `supplier` as default; delete `org:admin` and
   `org:member`.
3. **Keys** (§3) into the platform's environment, `ALLOWED_ORIGINS` with the real portal
   hostnames (§4), and the webhook endpoint with its secret (§6).
4. **Organizations → Settings → Allow user-created organizations** off (§1).
5. **Account Portal → Redirects** to the internal portal's `/home` (§7).

---

## Symptom → cause

| What you see | Likely cause |
|---|---|
| Signed in, but every route bounces you back | Role slug mismatch — `getUserRole()` returned `null`. Check the slug spelling, and that the member holds one of the four roles (§1). |
| 401 from the API, token looks valid | The portal's origin is missing from `ALLOWED_ORIGINS` (§4). Server log: `token_party_not_allowed`. |
| Server won't start, `SettingsError` on `ALLOWED_ORIGINS` | Not a JSON array (§4). |
| "Must belong to an organization" at sign-in | Expected: the user was removed from their org and may not create one (§1). Re-invite them, or delete the user. |
| "Setup your organization" at sign-in | The user has no membership and may create organizations — the dashboard toggle is on (§1). |
| Signed in, everything empty, no errors | No **active** organization → `org_id = None` (§1). |
| 403 `SUPPLIER_NOT_LINKED` | A `supplier`-role user with no `Supplier.contact_id` pointing at them. Expected until the invitation carrying `supplier_id` metadata is accepted. |
| Browser CORS error on every request | Same as the 401 row — one setting, two symptoms (§4). |
| Roles work locally, not in staging/production | `ALLOWED_ORIGINS` is per-environment; each `server/.env.<env>` needs its own origins. |
| Role change in Clerk not taking effect | Cached 60s, invalidated by membership webhooks. If webhooks aren't delivering, it degrades to the TTL (§6). |
| Every webhook delivery 401s | Wrong `whsec_` for this instance, or the variable never reached the process — check the running process's environment, not the file (§6). |
| No webhook deliveries at all | Endpoint on the wrong instance, or the tunnel is down (§6). |
| ngrok `ERR_NGROK_320` | The authtoken belongs to a different account than the domain — check the host `ngrok.yml`, which beats the env var (§6). |
| ngrok `ERR_NGROK_105` | A resource id (`rd_`, `cr_`, `ak_`) pasted instead of the authtoken (§6). |
| Webhook deliveries 404 | The path is `/api/v1/webhooks/clerk` (§6). |
| Container exits at startup naming `CLERK_WEBHOOK_SIGNING_SECRET` | `REQUIRED_ENV_VARS` in `server/scripts/docker-entrypoint.sh` — set the secret. |
| Deliveries succeed, database unchanged | Not setup — look for `webhook_event_stale` or a missing-row warning in the handler logs. |
| `make clerk-seed-users` fails naming a role | The instance does not have it yet — `make clerk-apply-roles` first. |
| `make clerk-apply-roles` fails: Organizations not enabled | `make clerk-apply-config` first. |
| `apply-roles` reports a role it kept | A member or an invitation still holds it; move them to a listed role and re-run. |
| `make clerk-check-config` fails | The instance was changed in the dashboard; the message says how to keep either side. |
| Sign-in fails for a seeded user with the right password | `make clerk-apply-config` was not run — password sign-in or the HIBP relaxation is missing (§1). |
