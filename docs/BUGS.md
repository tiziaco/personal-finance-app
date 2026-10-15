# Known bugs

Behaviour that is **wrong today**, in code that is already merged. Each entry says what
is broken, how to reproduce it, why it has gone unnoticed, and what fixing it involves,
so it can be picked up cold.

A bug leaves this file when it is fixed. If a test pins the broken behaviour, invert it
rather than delete it, so the fix is what makes it pass.

**This file is not [`TODO.md`](./TODO.md).** The test is whether anything is wrong right
now. A bug is a defect in merged code; a TODO is a decision deferred to the change that
should make it, in code that is correct as it stands. "There is no row-level
security" is a TODO — the query layer already scopes every read, so nothing leaks. "The
settings dialog has no side gutter on a phone" is a bug — it is in `main` and any phone
shows it.

---

## Server

### The app connects to Postgres as a superuser that owns every table

The `db` service in both compose files reads `server/.env.<env>`, so the pgvector image's
init creates `POSTGRES_USER` as the cluster's **superuser**. The server and the one-shot
`migrate` service then connect with those same credentials. The role the app runs as is
therefore `rolsuper = t`, `rolbypassrls = t`, and owns every table. Nothing limits what a
bug in a route, or an injection through one, can do to the schema or to other users'
rows.

**Reproduce:** against any environment's database, as the server's connection:
`SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user;`

**Why it has gone unnoticed:** nothing needs less. Tenancy is enforced in the query
layer (the user id from the JWT), there is no row-level security for the role to bypass,
and one role is the simplest thing that works for a dev stack.

**Fixing it** is role separation: an owner role for Alembic, and a restricted app role
for the server — not superuser, not owner, no `BYPASSRLS` — with `GRANT`s on the tables
(and `ALTER DEFAULT PRIVILEGES` so tables from later migrations are covered). It touches
`server/.env.*` and `.env.example`, both compose files (the `migrate` and `server`
services need different credentials), `server/scripts/migrate.sh`, and the deploy notes
in the root `CLAUDE.md`. It is also the precondition for any future RLS: until the app
role can't bypass policies, every policy is decoration.

While there: `server/scripts/ensure-db-user.sh` is invoked by nothing, and it assumes a
`postgres` superuser that the image never creates once `POSTGRES_USER` is set. Either
make it the bootstrap for the new roles or delete it.

### Every rate limit collapses into one shared bucket behind a proxy

`server/app/core/limiter.py:14` keys on `get_remote_address`, which reads
`request.client.host`. `server/Dockerfile:98` starts uvicorn with no
`--forwarded-allow-ips`, and no proxy-headers middleware is registered, so forwarded
headers are not trusted and `request.client.host` is whatever connected to the server.
Behind a reverse proxy, that is the proxy. `docker-compose.prod.yml` publishes no ports
and Traefik is the only ingress, so on staging and production every caller shares one
bucket: a route's per-minute limit becomes a limit for the whole platform, and one busy
user locks everyone else out of it.

**Reproduce:** not on the dev stack — `docker-compose.dev.yml` publishes `8100:8000`, so
the browser connects to the container directly and every caller keys on its own address.
It reproduces on the first deploy behind Traefik: two users, two machines, one counter.

**Why it has gone unnoticed:** nothing is deployed, and no endpoint is called often
enough for one user to exhaust a limit alone.

**Fixing it** is `--forwarded-allow-ips` set to the proxy's address — **not** `*`, which
trusts a header any client can forge and turns an IP limit into no limit. On a Dokploy
host the proxy is on `dokploy-network`, so the value belongs with the other
deploy-environment settings rather than baked into the Dockerfile's `CMD`.

Related, and worth settling in the same change: `SlowAPIMiddleware` is never registered —
`server/app/main.py:88` sets `app.state.limiter` and nothing else — so
`settings.rate_limits.DEFAULT` is inert and only routes with an explicit
`@limiter.limit(...)` are limited at all. Either register the middleware or drop
`default_limits`, so the config stops implying a limit that doesn't exist.

### A test that trips a rate limit gets a 500, and limits leak between tests

slowapi's 429 handler (`_rate_limit_exceeded_handler`) reads `request.app.state.limiter`,
which only `lifespan()` sets (`server/app/main.py:88`). No client fixture in
`server/tests/conftest.py` runs the lifespan — they call the app through
`ASGITransport` — so under test the handler raises `AttributeError: 'State' object has
no attribute 'limiter'` and a tripped limit answers 500. The limiter's in-memory storage
is also a module-level singleton, and every test client has the same address, so requests
from one test count against the next test's limit.

**Reproduce:** a test that calls a decorated route once more than its limit allows —
31 calls to `renameConversation`, whose `CHAT` limit is 30 a minute — and asserts 429.

**Why it has gone unnoticed:** no test asserts a 429, and no single test sends enough
requests to trip a limit. The carry-over surfaces only once the suite is large enough
for one route's calls to add up within a minute.

**Fixing it** is an autouse fixture in `server/tests/conftest.py` that sets
`app.state.limiter = limiter` and calls `limiter.reset()` before every test, whichever
client fixture it uses — plus the reproduce test above, which fails first.

---

## Web app

### The settings dialog has no side gutter on a phone, and a fixed height

`SettingsDialog` (`web-app/packages/components/src/settings/settings-dialog.tsx:60`)
sets `max-w-2xl!` on `DialogContent`. The `!` overrides the primitive's `sm:max-w-md`,
and with it `max-w-[calc(100%-2rem)]` — the 1rem gutter each side.
Below 42rem the dialog is `w-full` with nothing narrowing it, so it runs edge to edge; the
200px rail (`w-50`) stays beside the content, which is left about 175px on a 375px screen.
`h-125` is a fixed 500px, so on a screen shorter than that the dialog is clipped top and
bottom — it is centred with a translate, not scrolled.

**Reproduce:** open the app at 375px wide, open Settings from the sidebar. Then
rotate to landscape.

**Why it has gone unnoticed:** the app is a desktop dashboard, and the sidebar that
holds the Settings trigger is itself a sheet on a phone, so reaching the dialog there is
already a detour.

**Fixing it:** `sm:max-w-2xl` instead of `max-w-2xl!` (`cn` merges it over the primitive's
`sm:max-w-md`, and the gutter survives); `h-[min(31.25rem,calc(100dvh-2rem))]`; below `sm`,
stack the rail above the content as a row of tabs (`flex-col sm:flex-row` on the wrapper,
`flex-row sm:flex-col` on `SidebarMenu`, the footer slot hidden). Keep the sidebar
primitives — the app renders the dialog inside a `SidebarProvider`. A layout test that
asserts the class contract (jsdom has no layout) fails first.

### The server-status dot pings "healthy" while it shows an error

`ServerStatusIndicator` (`web-app/packages/components/src/settings/server-status-indicator.tsx`)
picks the dot's colour from `error` first — any error is red — but draws the pulsing ring
whenever `status?.status === "healthy"`, without looking at `error`. During an outage that
is not a degraded 503 (a 500, an expired token, the server gone), `useServerStatus` keeps
the error and TanStack Query keeps the last healthy `data`, so the dot is red **and**
pulsing, in red: a live-looking signal on a dead server.

**Reproduce:** with the app open and the settings dialog showing the indicator, stop the
API server and wait for the next 30-second refetch.

**Why it has gone unnoticed:** it needs the API to die after a healthy load, and the
colour is right; only the ring is wrong. The component's test covers each state alone,
not stale healthy data with an error.

**Fixing it** is gating the ring on the same condition as green — no `error` and a
healthy status — with a test for the combination that fails first.

### The first page load after sign-in fires its queries without a token

`useApiFetch` (`web-app/packages/api-client/src/use-api-fetch.ts:98`) binds `getToken` from
`useAppAuth()` and sends whatever it returns. Right after a Clerk sign-in, before the
session is loaded, `getToken()` resolves to `null`, `apiRequest` sends the request with no
`Authorization` header, and the server answers 401. Nothing holds the generated hooks back
until `isLoaded`, so every query a page fires on its first render goes out bare.

**Reproduce:** sign out, sign in, and land on `/transactions`. `GET /api/v1/transactions`
and `/categories` go out with no `Authorization` header, the server logs
`no_auth_header_present` and answers 401, and the table shows "Something went wrong"
until the page is reloaded. With step 5a, `/home` does the same for `analytics/dashboard`,
`transactions?limit=10` and `categories`.

**Why it has gone unnoticed:** it only happens on the first render straight after the
sign-in redirect; any later navigation or a reload has the token. Both wave-2 workers hit it
in their hand checks on 15 Oct 2026.

**Fixing it** belongs in the shared fetch layer, not in each page: hold queries until the
session is loaded (for example, `QueryProvider` gating on `isLoaded`, or `useApiFetch`
waiting for a token before it sends), with a test that renders a query before
`isLoaded` and expects no request. It touches the hand-written `api-client` files, so it is a
change of its own, never part of a feature step.
