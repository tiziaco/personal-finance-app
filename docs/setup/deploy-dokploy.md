# Deploying with Dokploy

Operational facts for deploying `docker-compose.prod.yml` behind Dokploy's Traefik
instance. Companion to the **Deploying** section of the root [`CLAUDE.md`](../../CLAUDE.md):
that section covers `make deploy-check` and what it proves; this doc covers what it
cannot exercise — the Traefik side, the origins, and the build args.

The file deploys four long-running services and a one-shot: `internal-portal`,
`supplier-portal` and `server` are routable, `db` is not, and `migrate` runs to
completion before `server` starts.

---

## How Dokploy actually configures Traefik

Established from the Dokploy documentation and source, not assumed:

- **Providers:** Docker + Swarm with `exposedByDefault: false`, plus a file provider for
  shared middleware. For a Compose application, routing comes from **Docker labels** —
  not from a separately generated config.
- **Entrypoints:** `web` (port 80), `websecure` (port 443).
- **Cert resolver:** named `letsencrypt`, HTTP challenge. Applied only to `websecure`
  routers, never to `web` — a `tls.certresolver` label enables TLS on whatever entrypoint
  its router is bound to, so putting it on the `web` router would make port 80 expect a
  TLS handshake. That is why `docker-compose.prod.yml` declares two routers per service
  (`<name>-web` and `<name>-secure`) instead of one router with a variable entrypoint.
- **Network:** `dokploy-network`. Traefik is pinned to it. **A Compose deployment lands
  only in its own project network unless the compose file joins `dokploy-network`
  explicitly** — this repo's `docker-compose.prod.yml` does, on each routable service.
  This is a known, still-open Dokploy issue
  ([#3435](https://github.com/Dokploy/dokploy/issues/3435)) and the single most common
  cause of a deploy that builds cleanly and then 404s. If a first deploy 404s, check this
  before anything else.

**Dokploy's Domains tab and hand-written labels are both labels, not two different
mechanisms.** Configuring a domain in the Domains UI and hand-writing a `Host()` label
for the same service both produce Traefik router labels. Doing both for the same
service yields two routers matching the same `Host()` rule, which is ambiguous —
confirmed by Dokploy issue [#3222](https://github.com/Dokploy/dokploy/issues/3222)
(the Domains tab does not show label-configured domains, because hand-written labels are
a recognised, separate path). **This project hand-writes every label in
`docker-compose.prod.yml` and leaves the Domains tab untouched.** Do not add a domain
there for a service this file already labels.

**Router and service names carry `${COMPOSE_PROJECT_NAME}`**, so several stacks from
this template can share one Traefik without their names colliding.

Sources: [Domains — Docker Compose](https://docs.dokploy.com/docs/core/docker-compose/domains),
[Domains](https://docs.dokploy.com/docs/core/domains),
[Traefik configuration](https://deepwiki.com/Dokploy/dokploy/8.2-traefik-configuration),
[#3435](https://github.com/Dokploy/dokploy/issues/3435),
[#3222](https://github.com/Dokploy/dokploy/issues/3222).

---

## `ALLOWED_ORIGINS` gates auth, not just CORS

It feeds CORS **and** the Clerk `azp` token-party check — the mechanism, and the JSON
array it must be, are in [`clerk.md`](./clerk.md) §4. What it means for a deploy:

**Both portal origins** — the real `https://` hostnames behind `INTERNAL_PORTAL_DOMAIN`
and `SUPPLIER_PORTAL_DOMAIN` — must be listed for the matching environment
(`server/.env.staging` / `server/.env.production`), or a structurally valid,
correctly-signed Clerk token is rejected on arrival. **A missing entry does not look like
a config error; it looks like broken auth** — `401` with a `token_party_not_allowed` log
line, not a startup failure. Missing only one of the two breaks only that portal, which
makes it look like a portal bug.

It matters more than it looks because the browser calls the API **directly,
cross-origin**: there is no server-side proxy hop hiding the origin. This is unexercised
by anything short of a real deploy — no browser, no Clerk, no CORS preflight runs during
`make deploy-check`.

---

## Both portal images get the internal portal's build args

`NEXT_PUBLIC_*` values are inlined into the bundle at build time, so they are build
args, not runtime env. Compose resolves `build.args` from the invoking shell's
environment, never from a service's own `env_file:`, and the root Makefile's `-include`
exports only `web-app/apps/internal-portal/.env.local`. So both images are built with
the internal portal's `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` and `NEXT_PUBLIC_API_URL`.

Harmless while both portals share one Clerk instance and one API origin. The day they
must differ, both images ship the internal portal's values with nothing warning —
`deploy-check` asserts only that each image baked its own `APP_NAME`. The limit is in
the compose file, not the Makefile: both services read the same variable names
(`${NEXT_PUBLIC_API_URL}`, `${NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY}`), so on Dokploy too
they get one value each. Tracked in [`../TODO.md`](../TODO.md).

---

## What `make deploy-check` does not prove

`make deploy-check` (`scripts/deploy-check.sh`) parses the compose file, builds both
portal images and the server image, brings the stack up under `APP_ENV=staging` (or
`production`), and asserts that each portal image baked its own `APP_NAME`, that
`migrate` exits 0, that `server` reaches `healthy` through its own healthcheck, and that
nothing is published to the host. **It does not route a single request through Traefik.**

Nobody has exercised the current label set against a real Traefik instance. Before the
first real deploy, review each of the following by hand against the Dokploy facts above —
a `docker compose -f docker-compose.prod.yml config` render is enough, no server needed:

- `traefik.enable=true` is present on `internal-portal`, `supplier-portal` and `server`,
  and not on `db` or `migrate`, which are not routable.
- `traefik.docker.network=dokploy-network` is present on all three routable services.
- Each declares **two** routers — `-web` (entrypoint `web`, no TLS) and `-secure`
  (entrypoint `websecure`, `tls.certresolver=letsencrypt`) — both pointing at the same
  `traefik.http.services.<name>.loadbalancer.server.port`.
- That port matches what the container listens on: `3000` for **both** portals (3002 is
  a dev host mapping only) and `8000` for `server`.
- The `server` routers exclude `/metrics`: `Host(...) && !PathPrefix(`/metrics`)`. That
  endpoint carries no auth, and a bare `Host()` rule would route it publicly.
- `INTERNAL_PORTAL_DOMAIN`, `SUPPLIER_PORTAL_DOMAIN` and `API_DOMAIN` are set to real
  hostnames in the Dokploy environment — nothing resolves them locally, so a typo renders
  a label that matches no traffic instead of erroring.

None of this is exercised until the first deploy. A wrong container port, a router
pointing at a service that is not declared, or a missing `dokploy-network` join each
surfaces there — as a 404 with nothing in the application logs to explain it, because
the request never reached the application.

---

## Also unproven until a first deploy

- **No TLS.** The `letsencrypt` cert resolver's HTTP challenge is first exercised on a
  real deploy — there is nothing to issue a certificate for locally.
- **No HTTP→HTTPS redirect.** The `-web` routers carry no redirect middleware, so the
  portals and the API also answer on plain HTTP until one is added.
- **No Dokploy.** Its label injection, build pipeline, and `dokploy-network` creation are
  unexercised by anything in this repo.
- **No Clerk production instance.** Production keys, the production origins registered in
  Clerk, and the webhook endpoint pointing at `API_DOMAIN`
  ([`clerk-webhooks.md`](./clerk-webhooks.md)) are set by hand per environment.

---

## If a deploy builds cleanly and then 404s

In order of likelihood, given the facts above:

1. The service is not on `dokploy-network` (check `networks:` in
   `docker-compose.prod.yml`, and that `docker network create dokploy-network` — or its
   Dokploy-managed equivalent — has actually run on the host).
2. A domain was also added in the Dokploy Domains tab for a service this file already
   labels, producing two ambiguous routers for the same `Host()`.
3. `INTERNAL_PORTAL_DOMAIN` / `SUPPLIER_PORTAL_DOMAIN` / `API_DOMAIN` in the Dokploy
   environment does not match the hostname actually being requested.

If it serves pages but every API call fails with `401`, it is not routing:
see **`ALLOWED_ORIGINS` gates auth** above.
