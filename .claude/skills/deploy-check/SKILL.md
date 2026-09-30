---
name: deploy-check
description: Deploying to staging or production with docker-compose.prod.yml on a Dokploy/Traefik host, and what `make deploy-check` does and does not prove. Use when changing docker-compose.prod.yml, running make deploy-check, preparing a deploy, or triaging a deployed stack that 404s or looks like broken auth.
---

# Deploying

`docker-compose.prod.yml` is the deploy file, and it serves **both** staging
and production — the environment is `APP_ENV`, not a second file. It publishes
no ports: a reverse proxy is the only ingress, and on a Dokploy host that proxy
is Traefik, discovering the containers through the labels in the file.

```bash
make deploy-check                     # staging (default)
make deploy-check DEPLOY_ENV=production
```

It runs under its own compose project, so a running dev stack is untouched, and
it tears itself down afterwards. It needs `server/.env.<env>` (gitignored, never
committed) and, once per machine, `docker network create dokploy-network` — the
deploy file declares that network `external` because a Dokploy host provides it.

**What it proves:** the file parses under `APP_ENV`; both portals build as
genuinely distinct images with their own `APP_NAME`; a failed migration fails the
stack instead of starting the server against a stale schema; the server reaches
healthy with no ingress but its own healthcheck; nothing publishes a host port.

**What it does not prove:** the Traefik labels — nothing routes a request through a
proxy — nor that `ALLOWED_ORIGINS` lists both portal origins, which gates the Clerk
`azp` check as well as CORS, so a missing one looks like broken auth. Both portal
images are also built with the same `NEXT_PUBLIC_*` values. The label checklist, the
Dokploy facts and a 404 triage are in
[`docs/setup/deploy-dokploy.md`](../../../docs/setup/deploy-dokploy.md).
