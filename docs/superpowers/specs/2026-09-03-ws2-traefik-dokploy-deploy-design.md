# WS2 — Deploy compose repair and Traefik labels

**Date:** 2026-09-03
**Status:** Specified, not started
**Supersedes:** the WS2 section of `2026-08-24-template-hardening-design.md`
**Depends on:** nothing outstanding (WS1, WS3, WS4, WS5, WS6 complete)

---

## Context

The parent tracker scoped WS2 as "Traefik in dev compose + Dokploy labels". Two of its
assumptions did not survive contact with the details, and a third question — how to
verify the result with no server to deploy to — took most of the design effort before
resolving into a deliberately small answer.

**There is no deployment target yet.** No Dokploy server is running, no domains are
reserved. WS2 cannot be validated by deploying.

**A Traefik service in `docker-compose.dev.yml` is the wrong shape.** The original plan
put Traefik in the dev stack so labels could be exercised. But labels live in the
*deploy* compose file, so a dev-side Traefik would exercise a second copy of them, and
two copies drift. Worse, `NEXT_PUBLIC_*` values are inlined at image build time
(`web-app/Dockerfile:46-58`), so routing dev through hostnames would mean rebuilding
both portal images every time you crossed between modes.

**A full local staging environment was designed, then descoped.** The design — the
deploy stack fronted by Traefik and published through the existing ngrok tunnel, phone-
reachable over real HTTPS — is preserved in Appendix A. It was dropped because ngrok's
free plan grants exactly one static domain, and a large share of that design existed
only to survive that limit: path-based routing, router rules as variables, `PathPrefix`
exceptions for the endpoints outside `/api`, a `traefik.enable` variable to pick one
portal at a time. None of that is production shape and none of it survives a real
staging server, so it would be built to be deleted. It also could not exercise CORS at
all, because path routing makes the portal and API same-origin — while the VPS that
replaces it exercises CORS properly, on separate hostnames.

**What this workstream is, therefore:** repair the deploy compose file and write the
Traefik labels correctly. Verification stops at what the file itself can show — it
parses, both portals build as distinct images, the stack comes up healthy behind the
migration gate. The labels are reviewed, not exercised; they are verified for real on
the first deploy. The staging environment moves to a follow-on that begins when a VPS
exists (see Follow-on below).

The fork argument from the parent tracker decides the split. The compose repair must
land here, before the fork, because after it a broken deploy file costs twice. The
staging environment is mostly infrastructure configuration rather than repo code, so
deferring it past the fork is cheap in a way that deferring the repair is not.

---

## Findings — the current state of `docker-compose.prod.yml`

The parent tracker recorded this file as "stale and unparseable". It is worse than
that: it could not deploy even with its env files present.

| # | Defect | Evidence |
|---|---|---|
| 1 | Declares a single `web-app` service | `docker-compose.prod.yml:2`. The repo split into `internal-portal` and `supplier-portal` before WS1; the deploy file predates the split. |
| 2 | Passes no `APP_NAME` build arg | `web-app/Dockerfile:27` declares `ARG APP_NAME` and `:60` runs `pnpm --filter $APP_NAME build`. With the arg absent the filter is empty and the build cannot select an app. |
| 3 | `env_file` points at a path that does not exist | `:5` reads `./web-app/.env.local`. Env files live at `web-app/apps/*/.env.local`. `docker compose config` fails here first. |
| 4 | Publishes application ports to the host | `:20` (`3000:3000`) and `:61` (`8000:8000`). Wrong shape behind a reverse proxy. |
| 5 | Not attached to `dokploy-network` | `:103-104` declares only `app-network`. **Traefik cannot discover the containers at all** — see below. |
| 6 | Hardcodes the environment in six places | `APP_ENV: production` / `.env.production` at `:35, 39-40, 42, 59, 64-65, 67, 86-87`. Blocks any second environment. |

Not a defect, and worth preserving: the one-shot `migrate` release-phase service added
in `2e450bc` is well-judged — Dokploy offers no release-phase hook, `server` gates on it
via `service_completed_successfully`, and a failed migration fails the deploy while the
previous container keeps serving. WS2 keeps it exactly as is.

---

## How Dokploy actually configures Traefik

Established from the Dokploy documentation and source-derived references, not assumed:

- **Providers:** Docker + Swarm with `exposedByDefault: false`, plus a file provider
  watching `/etc/dokploy/traefik/dynamic/` for shared middleware. For Compose
  applications the routing comes from **Docker labels**, not from generated dynamic
  files: "at runtime, during the deployment phase, Dokploy automatically adds Traefik
  labels internally to your Docker Compose file."
- **Entrypoints:** `web` (80), `websecure` (443), HTTP/3 on 443. Dashboard on 8080.
- **Cert resolver:** named `letsencrypt`, HTTP challenge. Applied only to `websecure`
  routers, never to `web`.
- **Network:** `dokploy-network`. Traefik is pinned to it with
  `docker.network: dokploy-network`, and Compose deployments land only in their own
  project network unless the compose file joins `dokploy-network` explicitly. This is a
  known, still-open Dokploy issue (#3435) and the single most common cause of a deploy
  that builds cleanly and then 404s.

This corrects the parent tracker's framing of the UI-versus-labels choice. Both paths
are labels; the Domains tab is not a different mechanism. The decision to hand-write
them still stands — two routers matching the same Host is ambiguous, and hand-written
labels are the only version testable off Dokploy — but the reason is duplicate routers,
not competing systems. Dokploy issue #3222 (show label-configured domains as read-only
in the Domains tab) confirms hand-written labels are a recognised path.

Sources: [Domains — Docker Compose](https://docs.dokploy.com/docs/core/docker-compose/domains),
[Domains](https://docs.dokploy.com/docs/core/domains),
[Traefik configuration](https://deepwiki.com/Dokploy/dokploy/8.2-traefik-configuration),
[#3435](https://github.com/Dokploy/dokploy/issues/3435),
[#3222](https://github.com/Dokploy/dokploy/issues/3222).

---

## A constraint to carry to the first deploy

`ALLOWED_ORIGINS` (`server/app/core/config.py:208`) feeds **two** consumers:

- CORS (`server/app/api/middlewares/cors.py:22,28`)
- the `azp` token-party check shipped in WS3/F3 (`server/app/utils/auth.py:72`)

Every origin introduced at deploy time must be listed there for the matching
environment, or a structurally valid Clerk token is rejected on arrival. A missing entry
does not look like a config error; it looks like broken auth.

It matters more than it appears because the browser talks to the API **directly,
cross-origin**: `web-app/packages/api-client/src/use-api-fetch.ts:25` reads
`NEXT_PUBLIC_API_URL` in a client-side hook, and `apps/*/src/proxy.ts` turns out to be
Clerk middleware, not an API proxy. There is no server-side hop to hide the origin.

Nothing in this workstream exercises it — that is the point of the split, and it is the
first thing the follow-on should test.

---

## Decisions

| # | Decision | Rationale |
|---|---|---|
| D1 | **The application services are declared once**, in the deploy compose file, parameterised by `APP_ENV` | The repo already models environments as a variable: `Makefile:14` (`ENV`), validated at `:185` against `development\|staging\|production`, and `config.py` reads `.env.{environment}`. A second copy of the topology would drift, and you would exercise the copy while shipping the original. |
| D2 | **Hand-written labels**; the Dokploy Domains tab stays unused | Only version testable outside Dokploy. Carried from the parent tracker with the corrected rationale above. |
| D3 | **Plain `Host()` rules with the hostname as a variable** — `${INTERNAL_PORTAL_DOMAIN}` and siblings | No server exists, so no hostname is known. A variable defers the value without deferring the shape, and the local verification supplies `*.localhost` values. The `PathPrefix` machinery of Appendix A is not needed once a real staging server can hold three hostnames. |
| D4 | **Two routers per service** — `<name>-web` on `web` with no TLS, `<name>-secure` on `websecure` with `tls.certresolver=letsencrypt` | Both declared unconditionally, so there is no environment-conditional label. Locally the secure router is inert (nothing terminates TLS); in Dokploy both are live. A web+websecure pair is the ordinary production shape anyway. |
| D4a | **Rejected: a single router with `entrypoints=${TRAEFIK_ENTRYPOINT}`** | Does not work. A `tls.certresolver` label enables TLS on whatever entrypoint its router is bound to, so pointing that router at `web` would make it expect a TLS handshake on port 80 and plain HTTP would fail. Compose cannot conditionally omit a label, so only a second router can remove the TLS config. |
| D5 | **No local proxy verification.** The labels are reviewed, not exercised | A throwaway Traefik container plus `curl -H "Host: …"` was specified and then dropped. With a real staging server coming, it catches a label typo roughly one deploy cycle earlier, and a Dokploy redeploy costs minutes. What it would have proven — network membership, router-to-service wiring, container ports — gets proven on the first deploy instead, against the real proxy rather than a stand-in. The cost is recorded honestly under *What this does not prove*. |
| D7 | **Filename stays `docker-compose.prod.yml`** | User decision, 2026-09-03. Noted dissonance: it will serve staging too, so the name under-describes it. Renaming to `docker-compose.deploy.yml` is cheapest before any Dokploy config references the path; recorded so the option is not lost. |
| D8 | **Monitoring stays out of the deploy file for now** | Reverses the 2026-09-03 decision to add a `monitoring` profile, which was made when staging was in scope. Adding three services that cannot be exercised here, and whose production exposure is undecided (R6), is scope this workstream should not carry. The profile design is preserved in Appendix A for the follow-on. |
| D9 | **No committed `.env.staging.example`** | User decision, 2026-09-03. `server/.env.staging` is created locally and is already gitignored (`server/.gitignore:18`). |

---

## Scope

### 1. Repair the deploy compose

- Replace the single `web-app` service with `internal-portal` and `supplier-portal`,
  each with its own `APP_NAME` build arg and
  `env_file: ./web-app/apps/<name>/.env.local`, mirroring `docker-compose.dev.yml:2-38`.
- Replace `ports:` with `expose:` on both portals and on `server`. No application port
  reaches the host; the proxy is the only ingress.
- Parameterise the environment: `APP_ENV: ${APP_ENV:-production}` and
  `env_file: ./server/.env.${APP_ENV:-production}` at all six sites.
- Keep the `migrate` release-phase service, its `depends_on` gate, and the
  `${COMPOSE_PROJECT_NAME}-server` shared image tag unchanged.

### 2. Traefik labels and networking

For each of the three routable services (`internal-portal`, `supplier-portal`,
`server`), using the internal portal as the worked example:

```yaml
    networks:
      - app-network
      - dokploy-network
    labels:
      - traefik.enable=true                       # exposedByDefault is false
      - traefik.docker.network=dokploy-network
      - traefik.http.services.internal-portal.loadbalancer.server.port=3000
      # HTTP router
      - traefik.http.routers.internal-portal-web.rule=Host(`${INTERNAL_PORTAL_DOMAIN}`)
      - traefik.http.routers.internal-portal-web.entrypoints=web
      - traefik.http.routers.internal-portal-web.service=internal-portal
      # HTTPS router — inert in local verification, live in Dokploy
      - traefik.http.routers.internal-portal-secure.rule=Host(`${INTERNAL_PORTAL_DOMAIN}`)
      - traefik.http.routers.internal-portal-secure.entrypoints=websecure
      - traefik.http.routers.internal-portal-secure.tls.certresolver=letsencrypt
      - traefik.http.routers.internal-portal-secure.service=internal-portal
```

```yaml
networks:
  app-network:
    driver: bridge
  dokploy-network:
    external: true
```

`loadbalancer.server.port` is the **container** port — 3000 for both portals, 8000 for
the server; the supplier portal's `3002` is a host mapping that does not exist here.
Both routers point at the same service, declared once.

The HTTPS redirect middleware on the `-web` routers is added at first deploy, not here:
locally it would redirect every request into a port nothing is listening on.

### 3. A `deploy-check` Makefile target

Parses the file, builds both images, brings the stack up with `APP_ENV=staging`, waits
for `server` to report healthy behind the migration gate, then tears down. No proxy and
no ingress: the server's existing healthcheck (`curl -f http://localhost:8000/health`,
run inside the container) is what confirms the stack works with no published ports.
Reuses the `ENV` validation at `Makefile:181-193`.

It still needs `docker network create dokploy-network` once on the host, because the
deploy file declares that network `external` and compose refuses to start without it.
On a Dokploy box the network already exists, which is why `external` is correct there.

### 4. Documentation

Root `CLAUDE.md` gains a short note on what `make deploy-check` covers and — more
importantly — what it does not: the Traefik labels are unexercised until the first
deploy.

---

## Acceptance

1. `docker compose -f docker-compose.prod.yml config` parses with `APP_ENV=staging` and
   a `server/.env.staging` present.
2. Both portal images build, each with its own `APP_NAME`, producing two distinct images.
3. `make deploy-check` brings the stack up: `migrate` exits 0, then `server` reaches
   `healthy` through its own healthcheck, with no published ports.
4. A deliberately broken migration fails the stack rather than starting the server
   against a stale schema.
5. `docker port` shows no application container publishing to the host.
6. Every label is reviewed against the Dokploy reference above: `traefik.enable`,
   `traefik.docker.network`, both routers, the service reference, and the container port.
7. `make docker-run` (development) is unchanged and still serves 3000 / 3002 / 8100.

Criterion 7 is the regression guard: none of this may touch the dev workflow.

Criterion 6 is a review, not a test. It is the deliberate soft spot of this scope — see
*What this does not prove*.

---

## Out of scope

- A staging environment of any kind. See Follow-on.
- Local proxy verification of the labels (D5).
- Monitoring in the deploy file (D8).
- Renaming the deploy compose file (D7).
- The HTTPS redirect middleware, and anything else first meaningful at deploy time.
- Provisioning, DNS, or Dokploy project setup.

---

## Risks and open questions

**R1 — The Makefile's build-arg leak.** `Makefile:23` does
`-include web-app/apps/internal-portal/.env.local` with `.EXPORT_ALL_VARIABLES:`, so
both portal images build with the *internal* portal's Clerk key and API URL. Known and
recorded in WS1. Harmless while both portals share a Clerk instance and API host, but
criterion 2 should confirm the two images actually differ.

**R2 — `ALLOWED_ORIGINS` value format.** Read as `List[str]` with no env prefix
(`config.py:203-208`). The accepted encoding in the `.env` files (JSON array versus
comma-separated) was not verified while writing this spec — the example env files are
outside the readable set. Confirm against a working `.env.development` before writing
`.env.staging`.

**R3 — `server/.env.staging` must exist** for the check to run at all, since the deploy
file's `env_file` is not optional. Seeded from development values; never committed.

**R4 — Deferred, not resolved: production observability.** Whether Prometheus, Grafana
and cAdvisor ship with a deploy is undecided, and cAdvisor specifically reports on every
container on its host — on a Dokploy box, that includes other applications and Dokploy's
own containers. A decision for the follow-on, recorded here so it is not lost.

---

## What this does not prove

- **The labels are unexercised.** Nothing routes a request through Traefik. A wrong
  service reference, a wrong container port, a missing `traefik.docker.network` — each
  surfaces on the first deploy, not here. This is the accepted cost of D5 and the
  largest gap in this scope.
- **No browser, no Clerk, no CORS.** No login, no token, no `azp` check, no preflight.
- **No TLS.** The `letsencrypt` path is first exercised on deploy.
- **No Dokploy.** Its label injection, build pipeline and network creation are
  unexercised.
- **Images differ from production.** `NEXT_PUBLIC_*` is inlined at build.

What it does prove is narrower, but it is the part that fails *silently* today: the file
parses, both portals build as distinct images, migrations gate the server, and the stack
runs with nothing published to the host. Routing correctness rides on review plus the
first deploy — an accepted trade, given that a real staging server is the next step and a
Dokploy redeploy costs minutes.

---

## Follow-on — staging on a VPS

When a small VPS running Dokploy exists (roughly €5/month, plus about €10/year for a
domain; an `sslip.io`-style hostname derived from the server IP is worth checking
against Let's Encrypt rate limits as a way to start without buying one), it supersedes
Appendix A entirely and delivers what the local design could not:

- Three real hostnames, so plain `Host()` rules deploy unchanged from this spec — and
  **the labels get their first real exercise**, against Dokploy's own Traefik rather
  than a stand-in.
- **Cross-origin CORS exercised for the first time**, alongside the `azp` check.
- Real Let's Encrypt certificates on the `-secure` routers.
- Both portals reachable simultaneously, from a phone, over real HTTPS.
- Dokploy itself under test — its label injection, its `dokploy-network` attachment, its
  build pipeline. None of that is reachable from a laptop, and it is where the known
  failures live (#3435).
- The monitoring decision (D8, R6) taken with a real host to take it about.

It is mostly infrastructure configuration rather than repo changes, which is why
deferring it past the fork is cheap.

---

## Appendix A — the tunnelled staging design (superseded)

Retained because the research cost real work and the follow-on may reuse parts of it.
**Not in scope.** It was designed to run the whole stack behind the ngrok tunnel already
reserved for WS4 webhooks, reachable from a phone on real HTTPS.

**The constraint that shaped it.** ngrok's free plan grants **exactly one static domain
per account** — the dev domain is the only domain available on that plan. A
production-shaped topology wants three hostnames. Free tier also shows an interstitial
on HTML browser traffic, cookied for seven days per domain, which does not affect API or
webhook traffic.

Sources: [Free plan limits](https://ngrok.com/docs/pricing-limits/free-plan-limits),
[Static dev domains for all ngrok users](https://ngrok.com/blog/free-static-domains-ngrok-users).

**The workarounds it required**, each of which is why it was dropped:

- **Path routing on one host.** `PathPrefix(/api)` → `server`, everything else → a
  portal. Workable without client changes: `resolveBaseUrl()`
  (`use-api-fetch.ts:24-32`) strips trailing slashes and generated routes already begin
  with `/api/v1/`, so `NEXT_PUBLIC_API_URL` set to the bare tunnel origin composes
  correctly.
- **Extra prefixes.** `/health`, `/ready` and `/docs` sit outside the `/api/v1` prefix,
  so the server rule needed them explicitly or they would fall through to the portal and
  404. `/metrics` deliberately excluded from public routing.
- **Rules as variables**, since staging needed `Host(…) && PathPrefix(…)` where
  production wants plain `Host(…)`.
- **One portal at a time**, selected by `traefik.enable=${…_ENABLED:-true}`, because two
  portals sharing a root catch-all is an ambiguous match. The alternative — a Next.js
  `basePath` for the supplier portal — would have changed application code to serve a
  staging constraint.
- **Monitoring behind a `monitoring` compose profile**, with Grafana published on host
  port 3001 by the overlay rather than routed, because no hostname was available to
  spend on it. This is the design D8 defers; it is sound and can be lifted as-is.

**Why it was dropped.** Most of the above is scaffolding for a limitation a real staging
server removes, so it would be built to be deleted. It also could not exercise CORS —
path routing makes portal and API same-origin — which is precisely the check most likely
to fail on a first deploy. The `azp` check *would* have been exercised, since Clerk sets
`azp` to the frontend origin regardless of same-origin.

**Risks recorded against it**, still relevant to any tunnelled setup: proxy-awareness
across two hops (ngrok terminates TLS and forwards plain HTTP, so Clerk and Next.js must
trust `X-Forwarded-Proto`); Clerk origin registration; tunnel contention with
`make dev-tunnel`, which claims the same static domain; and free-tier bandwidth of 1GB
per month.
