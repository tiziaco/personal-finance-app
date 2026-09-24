# Known bugs

Behaviour that is **wrong today**, in code that is already merged. Each entry says what
is broken, how to reproduce it, why it has gone unnoticed, and what fixing it involves,
so it can be picked up cold.

A bug leaves this file when it is fixed. If a test pins the broken behaviour, invert it
rather than delete it, so the fix is what makes it pass.

---

## Server

### The app connects to Postgres as a superuser that owns every table

The `db` service in both compose files reads `server/.env.<env>`, so the pgvector image's
init creates `POSTGRES_USER` as the cluster's **superuser**. The server and the one-shot
`migrate` service then connect with those same credentials. The role the app runs as is
therefore `rolsuper = t`, `rolbypassrls = t`, and owns every table. Nothing limits what a
bug in a route, or an injection through one, can do to the schema or to other tenants'
rows.

**Reproduce:** against any environment's database, as the server's connection:
`SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user;`

**Why it has gone unnoticed:** nothing needs less. Tenancy is enforced in the query
layer (the org id from the JWT), there is no row-level security for the role to bypass,
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
