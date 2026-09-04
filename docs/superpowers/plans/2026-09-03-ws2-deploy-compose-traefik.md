# WS2 — Deploy Compose Repair and Traefik Labels Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `docker-compose.prod.yml` deployable again — two portal services, correct env paths, no published ports, environment as a variable — and give it the Traefik labels and network membership a Dokploy host needs, with a `make deploy-check` target that proves everything except the labels.

**Architecture:** One deploy compose file serves both staging and production, parameterised by `APP_ENV`; `docker-compose.dev.yml` is untouched. Routing is hand-written Docker labels on three services (`internal-portal`, `supplier-portal`, `server`), each joined to the external `dokploy-network` so Dokploy's Traefik can discover it. Verification is a shell script in the repo's existing `scripts/` idiom, driven by a thin Makefile target: it parses the file, builds the images, asserts `APP_NAME` reached each portal image, waits for the migration gate and the server healthcheck, and asserts no container publishes a host port. The Traefik labels are reviewed against the spec's Dokploy reference, not exercised — that is a deliberate, recorded gap.

**Tech Stack:** Docker Compose v2, Traefik v3 (Dokploy-managed), GNU Make, bash, FastAPI + Alembic (server), Next.js 16 standalone output (portals).

**Spec:** `docs/superpowers/specs/2026-09-03-ws2-traefik-dokploy-deploy-design.md`

## Global Constraints

- **`docker-compose.dev.yml` must not change.** Acceptance criterion 7 is the regression guard: `make docker-run` still serves 3000 / 3002 / 8100 unchanged. If a task tempts you to edit the dev file, stop — you have misread the task.
- **The `migrate` service is preserved verbatim** — its `image: ${COMPOSE_PROJECT_NAME}-server` shared tag, its `command`, its `REQUIRED_ENV_VARS=` opt-out, its `restart: "no"`, and `server`'s `depends_on: migrate: condition: service_completed_successfully`. Only its two hardcoded `production` strings become `${APP_ENV:-production}`.
- **No application port reaches the host in the deploy file.** `expose:`, never `ports:`. The proxy is the only ingress.
- **`server/.env.staging` and `server/.env.production` are never committed.** `server/.gitignore:18` already ignores `.env.staging`. Per spec D9 there is no committed `.env.staging.example`.
- **Filename stays `docker-compose.prod.yml`** (spec D7), even though it now also serves staging.
- **Monitoring stays out of the deploy file** (spec D8). Do not add prometheus, grafana or cadvisor.
- **The HTTPS-redirect middleware is out of scope.** Locally it would redirect into a port nothing listens on.
- **`loadbalancer.server.port` is the *container* port:** `3000` for both portals (`web-app/Dockerfile:80-81` — `EXPOSE 3000`, `ENV PORT=3000`), `8000` for the server. The supplier portal's `3002` is a dev host mapping and does not exist here.
- **Exact Dokploy values, copied from the spec:** entrypoints `web` (80) and `websecure` (443); cert resolver named `letsencrypt`, applied only to `websecure` routers; network named `dokploy-network`; `exposedByDefault: false`, so `traefik.enable=true` is mandatory.
- **Shell scripts follow the house style** of `scripts/check-contract.sh`: `#!/usr/bin/env bash`, `set -euo pipefail`, `SCRIPT_DIR` + `cd "$SCRIPT_DIR/.."`, a comment header that explains *why*, `==>` progress lines, `FAIL:` / `PASS:` verdicts.
- All `make` commands run from the repo root.

---

## File Structure

| File | Responsibility |
|---|---|
| `scripts/deploy-check.sh` | *Create.* The whole verification: parse, build, assert `APP_NAME` per image, migration gate, server health, no published ports. Written before the repair, so it fails first. |
| `Makefile` | *Modify.* A thin `deploy-check:` target calling the script, plus a help entry. No change to `COMPOSE_FILE`, which must stay `docker-compose.dev.yml`. |
| `docker-compose.prod.yml` | *Modify.* The six defects, then the Traefik labels and `dokploy-network`. |
| `CLAUDE.md` | *Modify.* A `## Deploying` section: what `deploy-check` covers and, more importantly, what it does not. |
| `docker-compose.dev.yml` | *Untouched.* Listed to make the constraint explicit. |

---

## Two deviations from the spec, decided while planning

Both were found by reading the files the spec cites. Each is implemented below; each is small to revert.

**A. Router and service names are prefixed with `${COMPOSE_PROJECT_NAME}`.** The spec's worked example uses bare names (`internal-portal`, `server`). Traefik router and service names are **global to the Traefik instance**, not scoped per compose project. A Dokploy host runs many projects against one Traefik; two of them defining `traefik.http.routers.server-web` collide, and one silently wins. `server` in particular is a name any project might pick. Deploying this repo's staging and production to the same box would collide with itself. `${COMPOSE_PROJECT_NAME}` is already a hard requirement of this file (`docker-compose.prod.yml:31,55` interpolate it into the image tag) and Compose always defines it, so the prefix costs nothing but line length.

**B. `container_name:` is dropped from the deploy file.** `docker-compose.prod.yml:3` sets `container_name: web-app`. A `container_name` is host-global: on a Dokploy box it collides with any other stack using the same name, and it blocks running two environments side by side. Compose's default `<project>-<service>-<n>` is already unique. `docker-compose.dev.yml` keeps its `container_name`s — one stack per laptop, and the readable names are worth it there.

---

## Task 1: Prerequisites — env files, network, and the `ALLOWED_ORIGINS` format

**This task is local machine setup. It produces no commit.** Nothing else in the plan runs until it is done. Spec risks R2 and R3.

**Files:**
- Create (local, gitignored, never committed): `server/.env.staging`
- Read only: `server/.env.development`, `server/.env.example`

**Interfaces:**
- Produces: a `server/.env.staging` file, an existing `dokploy-network` Docker network. Every later task's `make deploy-check` depends on both.

- [ ] **Step 1: Confirm the `ALLOWED_ORIGINS` encoding (spec R2)**

`server/app/core/config.py:203-208` reads it as a bare `List[str]` with `env_prefix=""`. Pydantic Settings parses a complex type from a JSON string, so the file almost certainly needs a JSON array — but the spec could not verify this, so verify it now rather than debug it on a deploy.

Run:

```bash
grep -n "ALLOWED_ORIGINS" server/.env.development server/.env.example
```

Expected: a line such as `ALLOWED_ORIGINS=["http://localhost:3000","http://localhost:3002"]`. Record which form the working development file uses; use exactly that form in `.env.staging`.

- [ ] **Step 2: Create `server/.env.staging`**

Copy the development file and change only what must differ. It is gitignored (`server/.gitignore:18`) and must never be committed.

```bash
cp server/.env.development server/.env.staging
```

Then edit it: set `APP_ENV=staging` if the file carries one, and leave `ALLOWED_ORIGINS` in the development form for now — nothing in this plan exercises CORS, and the real values are unknowable until domains exist. Add a comment at the top of the file recording that.

- [ ] **Step 3: Verify it is not tracked**

Run: `git check-ignore -v server/.env.staging`
Expected: a line naming `server/.gitignore:18`. If the command prints nothing, **stop** — the file would be committable, and it holds secrets.

- [ ] **Step 4: Create the `dokploy-network` network**

The deploy file declares it `external` because a Dokploy host already provides it. Locally it must be created once.

```bash
docker network create dokploy-network
```

Expected: a network id, or `Error response from daemon: network with name dokploy-network already exists` — both are fine.

- [ ] **Step 5: Confirm the portal env files exist**

Run: `ls web-app/apps/internal-portal/.env.local web-app/apps/supplier-portal/.env.local`
Expected: both listed. If either is missing, copy it from the matching `.env.example` per the root `CLAUDE.md` before continuing — the deploy file's `env_file` entries are not optional.

- [ ] **Step 6: No commit**

This task deliberately produces none. Confirm with `git status --porcelain` that the working tree is clean.

---

## Task 2: The failing check — `scripts/deploy-check.sh` and `make deploy-check`

Write the verification before the repair, and watch it fail on the real defects. On the un-repaired file it fails at the very first step, on defect 3 (`env_file` pointing at `./web-app/.env.local`, a path that never existed).

**Files:**
- Create: `scripts/deploy-check.sh`
- Modify: `Makefile:1` (`.PHONY`), `Makefile:32-34` (help), and a new target after `check-contract` (`Makefile:111-112`)

**Interfaces:**
- Consumes: `server/.env.staging` and the `dokploy-network` network from Task 1.
- Produces: `make deploy-check` — exit 0 on success, non-zero with a `FAIL:` line otherwise. Tasks 3, 4 and 5 use it as their pass/fail gate. The script honours `DEPLOY_ENV` (default `staging`) and runs under its own compose project name `deploy-check`, so it can never touch a running dev stack.

- [ ] **Step 1: Write the script**

Create `scripts/deploy-check.sh` with exactly this content:

```bash
#!/usr/bin/env bash
# Verify docker-compose.prod.yml could deploy, without a deployment target.
#
# The deploy file drifted past the two-portal split and carried defects that
# no review caught: a service that no longer exists, an env_file path that
# never did, no APP_NAME build arg, application ports published straight to
# the host. Every one of them fails here, in seconds, instead of on a deploy.
#
# What this proves: the file parses under APP_ENV, both portals build as
# genuinely distinct images, migrations gate the server, the server reaches
# healthy through its own healthcheck, and nothing publishes to the host.
#
# What this does NOT prove: anything about the Traefik labels. Nothing here
# routes a request through a proxy — they are reviewed, and first exercised
# on a real deploy. See docs/superpowers/specs/
# 2026-09-03-ws2-traefik-dokploy-deploy-design.md, "What this does not prove".
#
# `docker compose` (v2) rather than the Makefile's DOCKER_COMPOSE: this script
# depends on v2 semantics — `<project>-<service>` default image names, and
# `ps -aq <service>` for a one-shot container that has already exited.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/.."

COMPOSE_FILE=docker-compose.prod.yml
DEPLOY_ENV="${DEPLOY_ENV:-staging}"
# Its own project name, so a running dev stack is never touched and the
# built image names are predictable.
PROJECT=deploy-check
COMPOSE=(docker compose -p "$PROJECT" -f "$COMPOSE_FILE")

case "$DEPLOY_ENV" in
  staging|production) ;;
  *)
    echo "FAIL: DEPLOY_ENV must be 'staging' or 'production' (got '$DEPLOY_ENV')."
    exit 1
    ;;
esac

ENV_FILE="server/.env.$DEPLOY_ENV"
if [ ! -f "$ENV_FILE" ]; then
  echo "FAIL: $ENV_FILE not found."
  echo "The deploy file's env_file is not optional. Seed it from your"
  echo "development values. It is gitignored and must never be committed."
  exit 1
fi

for app in internal-portal supplier-portal; do
  if [ ! -f "web-app/apps/$app/.env.local" ]; then
    echo "FAIL: web-app/apps/$app/.env.local not found."
    echo "Copy it from the matching .env.example — see the root CLAUDE.md."
    exit 1
  fi
done

# Hostnames have no defaults in the compose file on purpose: a wrong default
# would route a live deploy at a hostname nobody owns, and present as a 404
# with nothing in the logs to explain it. Nothing resolves these values; they
# exist so the labels render.
export APP_ENV="$DEPLOY_ENV"
export INTERNAL_PORTAL_DOMAIN="${INTERNAL_PORTAL_DOMAIN:-internal.localhost}"
export SUPPLIER_PORTAL_DOMAIN="${SUPPLIER_PORTAL_DOMAIN:-supplier.localhost}"
export API_DOMAIN="${API_DOMAIN:-api.localhost}"
export NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL:-https://$API_DOMAIN}"

teardown() {
  echo "==> Tearing down"
  "${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
}
trap teardown EXIT

echo "==> 1/5 Parsing $COMPOSE_FILE (APP_ENV=$DEPLOY_ENV)"
"${COMPOSE[@]}" config -q

echo "==> 2/5 Building both portals and the server"
"${COMPOSE[@]}" build internal-portal supplier-portal server

echo "==> 3/5 Checking each portal image baked its own APP_NAME"
# web-app/Dockerfile:65-66 re-declares ARG APP_NAME in the runner stage and
# promotes it to ENV, so the build arg is readable off the finished image.
# Without it `pnpm --filter $APP_NAME build` has an empty filter and the two
# portals are not distinct applications at all.
for app in internal-portal supplier-portal; do
  baked=$(docker image inspect -f '{{range .Config.Env}}{{println .}}{{end}}' \
    "$PROJECT-$app" | sed -n 's/^APP_NAME=//p')
  if [ "$baked" != "$app" ]; then
    echo "FAIL: image $PROJECT-$app baked APP_NAME='$baked', expected '$app'."
    echo "The APP_NAME build arg is not reaching the image."
    exit 1
  fi
done

echo "==> 4/5 Starting the stack"
# Not `set -e`-fatal: if a dependency fails, the explicit assertions below
# produce a better message than compose's "dependency failed to start".
"${COMPOSE[@]}" up -d || true

migrate_cid=$("${COMPOSE[@]}" ps -aq migrate)
if [ -z "$migrate_cid" ]; then
  echo "FAIL: the migrate container was never created."
  exit 1
fi
for _ in $(seq 1 90); do
  [ "$(docker inspect -f '{{.State.Status}}' "$migrate_cid")" = exited ] && break
  sleep 2
done
migrate_code=$(docker inspect -f '{{.State.ExitCode}}' "$migrate_cid")
if [ "$migrate_code" != 0 ]; then
  echo "FAIL: migrate exited $migrate_code; the server must not be serving."
  "${COMPOSE[@]}" logs migrate
  exit 1
fi
echo "    migrate exited 0"

server_cid=$("${COMPOSE[@]}" ps -aq server)
if [ -z "$server_cid" ]; then
  echo "FAIL: the server container was never created, though migrate exited 0."
  exit 1
fi
health=starting
for _ in $(seq 1 90); do
  health=$(docker inspect -f '{{.State.Health.Status}}' "$server_cid" 2>/dev/null || echo starting)
  [ "$health" = healthy ] && break
  if [ "$health" = unhealthy ]; then
    echo "FAIL: the server container went unhealthy."
    "${COMPOSE[@]}" logs server
    exit 1
  fi
  sleep 2
done
if [ "$health" != healthy ]; then
  echo "FAIL: the server did not reach healthy within 180s (last: $health)."
  "${COMPOSE[@]}" logs server
  exit 1
fi
echo "    server is healthy with no ingress but its own healthcheck"

echo "==> 5/5 Asserting nothing is published to the host"
published=""
for cid in $("${COMPOSE[@]}" ps -aq); do
  name=$(docker inspect -f '{{.Name}}' "$cid" | sed 's|^/||')
  map=$(docker port "$cid" || true)
  if [ -n "$map" ]; then
    published="$published  $name -> $(echo "$map" | tr '\n' ' ')"$'\n'
  fi
done
if [ -n "$published" ]; then
  echo "FAIL: the deploy stack publishes ports to the host:"
  printf '%s' "$published"
  echo "Behind a reverse proxy nothing should. Use expose:, not ports:."
  exit 1
fi

echo
echo "PASS: $COMPOSE_FILE parses, builds two distinct portal images, gates the"
echo "      server on migrations, and runs with nothing published to the host."
echo "NOTE: the Traefik labels are NOT exercised here. Nothing routes a request"
echo "      through a proxy. They are first proven on a real deploy."
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x scripts/deploy-check.sh
```

- [ ] **Step 3: Add the Makefile target**

Add `deploy-check` to the `.PHONY` list on `Makefile:1`, appending it after `check-contract`:

```makefile
.PHONY: help dev-preflight dev-tunnel gen-contract check-contract deploy-check docker-build docker-build-web docker-build-api docker-run docker-run-core docker-run-db docker-migrate docker-migrate-status docker-stop docker-logs docker-logs-core clean rebuild rebuild-core
```

Add the target immediately after `check-contract` (currently `Makefile:111-112`):

```makefile
# Verify the deploy compose file without a deployment target. Runs under its
# own compose project so a running dev stack is untouched, and tears itself
# down. DEPLOY_ENV selects the server env file (staging by default) — note
# this is separate from ENV, which the dev targets use.
deploy-check:
	@DEPLOY_ENV=$(DEPLOY_ENV) ./scripts/deploy-check.sh
```

Add `DEPLOY_ENV ?= staging` immediately after `ENV ?= development` on `Makefile:14`:

```makefile
ENV ?= development
# Which server/.env.<env> `make deploy-check` runs the deploy stack against.
DEPLOY_ENV ?= staging
```

Add a help entry after the `check-contract` line (`Makefile:34`):

```makefile
	@echo "  make deploy-check       - Verify docker-compose.prod.yml builds and runs (DEPLOY_ENV=staging)"
```

- [ ] **Step 4: Run the check and confirm it fails on the real defect**

Run: `make deploy-check`

Expected: it fails in `==> 1/5 Parsing docker-compose.prod.yml (APP_ENV=staging)` with a compose error naming `./web-app/.env.local` — the env_file path that never existed (spec defect 3). That is the first of six defects and confirms the check has teeth.

If it instead fails earlier with `FAIL: server/.env.staging not found` or `web-app/apps/.../.env.local not found`, Task 1 is incomplete — go back and finish it.

- [ ] **Step 5: Confirm the dev workflow is untouched**

Run: `docker compose -f docker-compose.dev.yml config -q`
Expected: exit 0, no output. The dev file was not edited and must still parse.

- [ ] **Step 6: Commit**

```bash
git add scripts/deploy-check.sh Makefile
git commit -m "build(ws2): add deploy-check, which fails on the current deploy compose

Verifies docker-compose.prod.yml without a deployment target: parse, build,
APP_NAME per portal image, the migration gate, server health, and no
published host ports. It fails today on the env_file path that never
existed. The Traefik labels are deliberately not exercised."
```

---

## Task 3: Repair the deploy compose

Fix defects 1, 2, 3, 4 and 6 from the spec's findings table. Defect 5 (`dokploy-network`) is Task 4.

**Files:**
- Modify: `docker-compose.prod.yml:1-105` (whole file)
- Modify: `scripts/deploy-check.sh` (step 4a only — one assertion)

**Interfaces:**
- Consumes: `make deploy-check` from Task 2.
- Produces: services named `internal-portal`, `supplier-portal`, `migrate`, `server`, `db`. Task 4 attaches labels to the first, second and fourth of those; the names it uses in router labels come from here.

- [ ] **Step 1: Run the check to confirm it is still red**

Run: `make deploy-check`
Expected: FAIL at step 1/5 on `./web-app/.env.local`.

- [ ] **Step 2: Replace the file**

Write `docker-compose.prod.yml` with exactly this content. The Traefik labels and `dokploy-network` are **not** here yet — Task 4 adds them.

```yaml
# The deploy compose file. Serves staging and production both: the environment
# is a variable, APP_ENV, exactly as Makefile's ENV and config.py's
# `.env.{environment}` already model it. There is no second copy of this
# topology to drift against.
#
# Nothing publishes a port. A reverse proxy (Traefik, on a Dokploy host) is the
# only ingress. `make deploy-check` asserts that.
#
# Deliberately no container_name: a container name is host-global, and a
# Dokploy box runs many stacks. Compose's <project>-<service>-<n> is unique.
# docker-compose.dev.yml keeps its names — one stack per laptop.
services:
  internal-portal:
    env_file:
      - ./web-app/apps/internal-portal/.env.local
    build:
      context: ./web-app
      dockerfile: Dockerfile
      args:
        APP_NAME: internal-portal
        # Every NEXT_PUBLIC_* value is inlined into the bundle at build time,
        # so these are build args, not runtime env. Required, not defaulted:
        # a default here bakes a wrong origin into a shipped image, and the
        # only symptom is the browser calling the wrong host.
        NEXT_PUBLIC_API_URL: ${NEXT_PUBLIC_API_URL:?required at build time - Next.js inlines it. Set it to the API's public origin, e.g. https://api.example.com}
        NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: ${NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY:?required at build time - Next.js inlines it. Set it in web-app/apps/*/.env.local (the Makefile exports it) or in the Dokploy environment}
        NEXT_PUBLIC_CLERK_SIGN_IN_URL: ${NEXT_PUBLIC_CLERK_SIGN_IN_URL:-/sign-in}
        NEXT_PUBLIC_CLERK_SIGN_UP_URL: ${NEXT_PUBLIC_CLERK_SIGN_UP_URL:-/sign-up}
    restart: unless-stopped
    # Documentation, not a binding: the proxy reaches this on the compose
    # network. The load-bearing part is the absence of `ports:`.
    expose:
      - "3000"
    networks:
      - app-network

  supplier-portal:
    env_file:
      - ./web-app/apps/supplier-portal/.env.local
    build:
      context: ./web-app
      dockerfile: Dockerfile
      args:
        APP_NAME: supplier-portal
        NEXT_PUBLIC_API_URL: ${NEXT_PUBLIC_API_URL:?required at build time - Next.js inlines it. Set it to the API's public origin, e.g. https://api.example.com}
        NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: ${NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY:?required at build time - Next.js inlines it. Set it in web-app/apps/*/.env.local (the Makefile exports it) or in the Dokploy environment}
        NEXT_PUBLIC_CLERK_SIGN_IN_URL: ${NEXT_PUBLIC_CLERK_SIGN_IN_URL:-/sign-in}
        NEXT_PUBLIC_CLERK_SIGN_UP_URL: ${NEXT_PUBLIC_CLERK_SIGN_UP_URL:-/sign-up}
    restart: unless-stopped
    # 3000, not 3002: that is the container port (web-app/Dockerfile:80-81).
    # 3002 is a host mapping that exists only in the dev file.
    expose:
      - "3000"
    networks:
      - app-network

  # One-shot release phase: applies Alembic migrations, then exits.
  # Dokploy deploys with `docker compose up -d --build` and offers no
  # release-phase hook, so the ordering has to live here. `server` is gated on
  # this exiting 0 — a failed migration fails the deploy and leaves the
  # previously running container serving the old image.
  # Shares `server`'s image tag by construction — keep the env config in sync.
  migrate:
    image: ${COMPOSE_PROJECT_NAME}-server
    build:
      context: ./server
      args:
        APP_ENV: ${APP_ENV:-production}
    command: ["bash", "scripts/migrate.sh"]
    volumes:
      - ./server/logs:/app/logs
    env_file:
      - ./server/.env.${APP_ENV:-production}
    environment:
      - APP_ENV=${APP_ENV:-production}
      - POSTGRES_HOST=db
      # Migrations don't call an LLM; a missing key must not fail a deploy.
      - REQUIRED_ENV_VARS=
    depends_on:
      db:
        condition: service_healthy
    # Must not restart, or `service_completed_successfully` never latches.
    restart: "no"
    networks:
      - app-network

  server:
    image: ${COMPOSE_PROJECT_NAME}-server
    build:
      context: ./server
      args:
        APP_ENV: ${APP_ENV:-production}
    expose:
      - "8000"
    volumes:
      - ./server/logs:/app/logs
    env_file:
      - ./server/.env.${APP_ENV:-production}
    environment:
      - APP_ENV=${APP_ENV:-production}
      - POSTGRES_HOST=db
    depends_on:
      db:
        condition: service_healthy
      migrate:
        condition: service_completed_successfully
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
    restart: unless-stopped
    networks:
      - app-network

  db:
    image: pgvector/pgvector:pg16
    env_file:
      - ./server/.env.${APP_ENV:-production}
    # No host port binding — DB is only accessible within the Docker network
    volumes:
      - postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    networks:
      - app-network

volumes:
  postgres-data:

networks:
  app-network:
    driver: bridge
```

Three things that were dropped, deliberately:

- `container_name: web-app` — see deviation B above.
- The three build args the Dockerfile never declares: `NEXT_PUBLIC_APP_URL`, `NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL`, `NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL`. `web-app/Dockerfile` declares only `APP_NAME`, `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `NEXT_PUBLIC_CLERK_SIGN_IN_URL` and `NEXT_PUBLIC_CLERK_SIGN_UP_URL`; passing the others earns a BuildKit warning and nothing else.
- The old comment claiming build args were "inherited from env_file". They are not — `env_file` is runtime-only and never feeds `build.args`. That comment is why the args were in list form and silently empty.

- [ ] **Step 3: Run the check and confirm it passes**

Run: `make deploy-check`

Expected, in order:

```
==> 1/5 Parsing docker-compose.prod.yml (APP_ENV=staging)
==> 2/5 Building both portals and the server
==> 3/5 Checking each portal image baked its own APP_NAME
==> 4/5 Starting the stack
    migrate exited 0
    server is healthy with no ingress but its own healthcheck
==> 5/5 Asserting nothing is published to the host

PASS: ...
==> Tearing down
```

The first run builds three images from cold and will take several minutes.

- [ ] **Step 4: Confirm the two portal images really are distinct**

Spec R1 is the reason to check by hand rather than trust step 3: `Makefile:23` includes the *internal* portal's `.env.local` with `.EXPORT_ALL_VARIABLES:`, so both images build with the same `NEXT_PUBLIC_*` values. They must still differ, because `APP_NAME` differs.

```bash
docker image inspect -f '{{.Id}}' deploy-check-internal-portal deploy-check-supplier-portal
```

Expected: two different sha256 ids. If they are identical, `APP_NAME` is not reaching the build and step 3 of the script should have caught it — investigate before continuing.

(The images survive teardown; only containers, volumes and networks are removed.)

- [ ] **Step 4a: Assert `APP_ENV` actually reached the running container**

`deploy-check` as written proves the file *parses* under `APP_ENV`, but nothing
proves the value landed inside a container. If one of the seven hardcoded
`production` sites were missed, the check would still pass — the gate would be
blind to the very defect this task fixes. Close it.

In `scripts/deploy-check.sh`, inside step `4/5`, immediately after the
`echo "    server is healthy..."` line, add:

```bash
# Defect 6 was the environment hardcoded to `production` in seven places.
# Parsing under APP_ENV does not prove the value reached a container: a missed
# `environment:` entry parses fine and runs the wrong environment. Assert it.
ran_as=$(docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$server_cid" \
  | sed -n 's/^APP_ENV=//p' | head -1)
if [ "$ran_as" != "$DEPLOY_ENV" ]; then
  echo "FAIL: the server container ran with APP_ENV='$ran_as', expected '$DEPLOY_ENV'."
  echo "A hardcoded environment is still present in $COMPOSE_FILE."
  exit 1
fi
echo "    server ran as APP_ENV=$ran_as"
```

Re-run `make deploy-check` after adding it; it must still pass.

- [ ] **Step 5: Confirm the dev stack still parses**

Run: `docker compose -f docker-compose.dev.yml config -q`
Expected: exit 0. The dev file must be byte-identical to what it was — confirm with `git diff --stat docker-compose.dev.yml` printing nothing.

- [ ] **Step 6: Commit**

```bash
git add docker-compose.prod.yml scripts/deploy-check.sh
git commit -m "fix(ws2): repair the deploy compose file

It could not deploy: a single web-app service that predates the two-portal
split, no APP_NAME build arg, an env_file path that never existed, and
application ports published straight to the host. The environment is now
APP_ENV rather than a hardcoded 'production' in six places, so one file
serves staging and production. The migrate release-phase gate is unchanged.

make deploy-check now passes."
```

---

## Task 4: Traefik labels and `dokploy-network`

Fix defect 5. This is the part the check cannot exercise; the step that stands in for a test is a review against the spec's Dokploy reference (acceptance criterion 6).

**Files:**
- Modify: `docker-compose.prod.yml` — `internal-portal`, `supplier-portal`, `server`, and the `networks:` block
- Modify: `scripts/deploy-check.sh` — add the `dokploy-network` precondition

**Interfaces:**
- Consumes: the service names from Task 3.
- Produces: Traefik routers named `${COMPOSE_PROJECT_NAME}-<service>-web` and `-secure`, and Traefik services named `${COMPOSE_PROJECT_NAME}-<service>`. Nothing later in this plan consumes them; the first consumer is Dokploy's Traefik.

- [ ] **Step 1: Add the `dokploy-network` precondition to the check**

In `scripts/deploy-check.sh`, insert this immediately after the `web-app/apps/*/.env.local` loop and before the `export APP_ENV=` block:

```bash
if ! docker network inspect dokploy-network >/dev/null 2>&1; then
  echo "FAIL: the 'dokploy-network' network does not exist."
  echo "The deploy file declares it external because a Dokploy host already"
  echo "provides it — that is why 'external' is correct there. Create it once"
  echo "on this machine:"
  echo "    docker network create dokploy-network"
  exit 1
fi
```

- [ ] **Step 2: Add the networks block**

Replace the `networks:` block at the bottom of `docker-compose.prod.yml`:

```yaml
networks:
  app-network:
    driver: bridge
  # Provided by the Dokploy host, where Traefik is pinned to it. A compose
  # deployment lands only in its own project network unless it joins this
  # explicitly (Dokploy issue #3435) — which is the single most common cause
  # of a deploy that builds cleanly and then 404s.
  # Locally: docker network create dokploy-network
  dokploy-network:
    external: true
```

- [ ] **Step 3: Add labels and network membership to `internal-portal`**

Replace that service's `networks:` block with:

```yaml
    networks:
      - app-network
      - dokploy-network
    # Router and service names are global to the Traefik instance, not scoped
    # per compose project, so they carry the project name: a Dokploy host runs
    # many stacks against one Traefik, and a bare `server-web` would collide.
    labels:
      - traefik.enable=true                       # Dokploy sets exposedByDefault: false
      - traefik.docker.network=dokploy-network
      - traefik.http.services.${COMPOSE_PROJECT_NAME}-internal-portal.loadbalancer.server.port=3000
      # HTTP router — no TLS config, so port 80 stays plain HTTP.
      - traefik.http.routers.${COMPOSE_PROJECT_NAME}-internal-portal-web.rule=Host(`${INTERNAL_PORTAL_DOMAIN:?set to the internal portal hostname, e.g. app.example.com}`)
      - traefik.http.routers.${COMPOSE_PROJECT_NAME}-internal-portal-web.entrypoints=web
      - traefik.http.routers.${COMPOSE_PROJECT_NAME}-internal-portal-web.service=${COMPOSE_PROJECT_NAME}-internal-portal
      # HTTPS router — a second router rather than a conditional label, because
      # tls.certresolver enables TLS on whatever entrypoint its router binds to,
      # and compose cannot omit a label conditionally.
      - traefik.http.routers.${COMPOSE_PROJECT_NAME}-internal-portal-secure.rule=Host(`${INTERNAL_PORTAL_DOMAIN}`)
      - traefik.http.routers.${COMPOSE_PROJECT_NAME}-internal-portal-secure.entrypoints=websecure
      - traefik.http.routers.${COMPOSE_PROJECT_NAME}-internal-portal-secure.tls.certresolver=letsencrypt
      - traefik.http.routers.${COMPOSE_PROJECT_NAME}-internal-portal-secure.service=${COMPOSE_PROJECT_NAME}-internal-portal
```

- [ ] **Step 4: Add labels and network membership to `supplier-portal`**

Same shape, different names and variable. Written out in full — do not derive it from the block above.

```yaml
    networks:
      - app-network
      - dokploy-network
    labels:
      - traefik.enable=true
      - traefik.docker.network=dokploy-network
      - traefik.http.services.${COMPOSE_PROJECT_NAME}-supplier-portal.loadbalancer.server.port=3000
      - traefik.http.routers.${COMPOSE_PROJECT_NAME}-supplier-portal-web.rule=Host(`${SUPPLIER_PORTAL_DOMAIN:?set to the supplier portal hostname, e.g. suppliers.example.com}`)
      - traefik.http.routers.${COMPOSE_PROJECT_NAME}-supplier-portal-web.entrypoints=web
      - traefik.http.routers.${COMPOSE_PROJECT_NAME}-supplier-portal-web.service=${COMPOSE_PROJECT_NAME}-supplier-portal
      - traefik.http.routers.${COMPOSE_PROJECT_NAME}-supplier-portal-secure.rule=Host(`${SUPPLIER_PORTAL_DOMAIN}`)
      - traefik.http.routers.${COMPOSE_PROJECT_NAME}-supplier-portal-secure.entrypoints=websecure
      - traefik.http.routers.${COMPOSE_PROJECT_NAME}-supplier-portal-secure.tls.certresolver=letsencrypt
      - traefik.http.routers.${COMPOSE_PROJECT_NAME}-supplier-portal-secure.service=${COMPOSE_PROJECT_NAME}-supplier-portal
```

The `loadbalancer.server.port` is `3000`, the same as the internal portal. That is correct and not a copy-paste error: both images are the same Next.js runtime listening on 3000 in their own network namespace. Two containers cannot collide on a container port.

- [ ] **Step 5: Add labels and network membership to `server`**

```yaml
    networks:
      - app-network
      - dokploy-network
    labels:
      - traefik.enable=true
      - traefik.docker.network=dokploy-network
      - traefik.http.services.${COMPOSE_PROJECT_NAME}-server.loadbalancer.server.port=8000
      - traefik.http.routers.${COMPOSE_PROJECT_NAME}-server-web.rule=Host(`${API_DOMAIN:?set to the API hostname, e.g. api.example.com}`)
      - traefik.http.routers.${COMPOSE_PROJECT_NAME}-server-web.entrypoints=web
      - traefik.http.routers.${COMPOSE_PROJECT_NAME}-server-web.service=${COMPOSE_PROJECT_NAME}-server
      - traefik.http.routers.${COMPOSE_PROJECT_NAME}-server-secure.rule=Host(`${API_DOMAIN}`)
      - traefik.http.routers.${COMPOSE_PROJECT_NAME}-server-secure.entrypoints=websecure
      - traefik.http.routers.${COMPOSE_PROJECT_NAME}-server-secure.tls.certresolver=letsencrypt
      - traefik.http.routers.${COMPOSE_PROJECT_NAME}-server-secure.service=${COMPOSE_PROJECT_NAME}-server
```

A plain `Host()` rule with no path component, so `/health`, `/ready`, `/` and `/metrics` all route here alongside `/api/v1/*`. That is deliberate: those endpoints sit outside the versioned prefix on purpose (`server/app/main.py:141-142`), and on a distinct API hostname there is nothing for them to collide with. Restricting `/metrics` is a deploy-time decision, not this file's.

**Do not add labels to `migrate` or `db`.** `migrate` exits; `db` must never be routable. With `exposedByDefault: false`, the absence of `traefik.enable=true` is what keeps them private.

- [ ] **Step 6: Run the check**

Run: `make deploy-check`
Expected: PASS, as in Task 3. The labels change nothing that the check observes — that is the point, and the reason step 7 exists.

- [ ] **Step 7: Review the rendered labels (acceptance criterion 6)**

The check cannot test these. Render them and read them.

```bash
INTERNAL_PORTAL_DOMAIN=internal.localhost \
SUPPLIER_PORTAL_DOMAIN=supplier.localhost \
API_DOMAIN=api.localhost \
NEXT_PUBLIC_API_URL=https://api.localhost \
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_render_only \
APP_ENV=staging \
docker compose -p deploy-check -f docker-compose.prod.yml config \
  | grep -A20 -E '^\s+labels:'
```

Every `:?` variable has to be supplied or `config` refuses to render at all —
that is the guard working, not a problem. The values are placeholders; nothing
resolves them.


Confirm, for each of the three services, all six of these:

1. `traefik.enable: "true"` is present. Without it Dokploy's Traefik ignores the container entirely (`exposedByDefault: false`).
2. `traefik.docker.network: dokploy-network` is present, and the service lists `dokploy-network` under `networks:`. A container not on that network is invisible to Traefik no matter what its labels say — Dokploy issue #3435.
3. `loadbalancer.server.port` is the **container** port: `3000`, `3000`, `8000`. A wrong value here resolves the container and then gets connection-refused, which presents as a 502, not a 404.
4. Both routers name the same service, and that name matches the `traefik.http.services.<name>` declared on the same container. A mismatch is a 404 with a healthy container behind it.
5. The `-web` router has `entrypoints: web` and **no** `tls` key of any kind; the `-secure` router has `entrypoints: websecure` and `tls.certresolver: letsencrypt`. A `tls.certresolver` on the `web` router would make port 80 expect a TLS handshake.
6. Every rule renders as `` Host(`<hostname>`) `` with the backticks intact and a non-empty hostname.

Also confirm `migrate` and `db` have **no** `traefik.*` labels at all.

- [ ] **Step 8: Confirm the hostname variables are genuinely required**

The `:?` guards are what stop a deploy from silently routing a hostname nobody owns.

Supply every other required variable, so the only thing missing is the
hostname:

```bash
APP_ENV=staging \
NEXT_PUBLIC_API_URL=https://api.localhost \
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_render_only \
docker compose -f docker-compose.prod.yml config -q
```

Expected: failure naming `INTERNAL_PORTAL_DOMAIN`, carrying the message written
into the label (`set to the internal portal hostname, e.g. app.example.com`).
If it succeeds, a `:?` is missing and a deploy could route a hostname nobody
owns.

- [ ] **Step 9: Commit**

```bash
git add docker-compose.prod.yml scripts/deploy-check.sh
git commit -m "feat(ws2): Traefik labels and dokploy-network on the deploy stack

Each routable service joins the external dokploy-network and carries
traefik.docker.network — without both, a compose deployment lands only in
its own project network and Traefik cannot discover it at all (Dokploy
#3435), which is the usual cause of a deploy that builds and then 404s.

Two routers per service: -web on the web entrypoint with no TLS, -secure on
websecure with the letsencrypt resolver. A single router taking the
entrypoint as a variable does not work, because tls.certresolver enables TLS
on whatever entrypoint its router binds to.

Names carry \${COMPOSE_PROJECT_NAME}: Traefik router and service names are
global to the instance, not per compose project.

The labels are reviewed, not exercised. Nothing routes a request through a
proxy until the first real deploy."
```

---

## Task 5: The migration gate, under a failure — and documentation

Acceptance criterion 4 asserts a *negative*: a broken migration must fail the stack rather than start the server against a stale schema. Nothing so far has seen `migrate` do anything but succeed.

**Files:**
- Modify: `CLAUDE.md` — a new `## Deploying` section
- Temporarily modify, then revert: `server/alembic/env.py`

**Interfaces:**
- Consumes: `make deploy-check` from Task 2, the repaired file from Tasks 3 and 4.
- Produces: documentation only. Nothing consumes this task.

- [ ] **Step 1: Break the migration deliberately**

Add a line at the very top of `server/alembic/env.py`, after the module
docstring on line 1:

```python
raise RuntimeError("deploy-check: deliberate migration failure, revert me")
```

`server/Dockerfile:71` copies `alembic/` into the image, and the deploy file
mounts no source (unlike the dev file, which bind-mounts `./server/alembic`).
So the break only takes effect once the image is rebuilt — which
`deploy-check`'s own `==> 2/5 Building` step does. Do not skip it.

- [ ] **Step 2: Run the check and confirm the stack fails correctly**

Run: `make deploy-check`

Expected: `FAIL: migrate exited 1; the server must not be serving.` followed by the migrate logs showing the `RuntimeError`. The run must **not** reach `==> 5/5`.

If it instead reports the server healthy, the `service_completed_successfully` gate is broken and must be fixed before this plan can be called done.

- [ ] **Step 3: Revert the break**

```bash
git checkout -- server/alembic/env.py
git status --porcelain server/alembic/env.py
```

Expected: the second command prints nothing.

- [ ] **Step 4: Re-run the check green**

Run: `make deploy-check`
Expected: PASS. This both confirms the revert and leaves the tree in a known-good state.

- [ ] **Step 5: Document it in `CLAUDE.md`**

Insert a `## Deploying` section immediately before the existing `## Environment Setup` heading:

```markdown
## Deploying

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

**What it does not prove: the Traefik labels.** Nothing routes a request through
a proxy. A wrong container port, a router pointing at a service that isn't
declared, a missing `dokploy-network` — each surfaces on the first real deploy,
not here. Reviewing them is the substitute, and the checklist is in
`docs/superpowers/specs/2026-09-03-ws2-traefik-dokploy-deploy-design.md`.

Also unproven, and worth knowing before a first deploy: `ALLOWED_ORIGINS`
(`server/app/core/config.py:208`) gates **both** CORS and the Clerk `azp`
token-party check (`server/app/utils/auth.py:72`). The browser calls the API
cross-origin — there is no server-side proxy hop — so every portal origin must
be listed for the deploying environment. A missing entry does not look like a
config error; it looks like broken auth.
```

- [ ] **Step 6: Add `deploy-check` to the Makefile help section list**

Confirm the help entry added in Task 2 reads correctly:

Run: `make help | grep deploy-check`
Expected: `  make deploy-check       - Verify docker-compose.prod.yml builds and runs (DEPLOY_ENV=staging)`

- [ ] **Step 7: Final regression check on the dev workflow (acceptance criterion 7)**

```bash
git diff --stat main -- docker-compose.dev.yml
```

Expected: nothing printed — the dev file is byte-for-byte unchanged. That, not a
parse, is the real guarantee: an unchanged file cannot have regressed.

A bare `docker compose -f docker-compose.dev.yml config -q` will **fail**, and
that is not a regression. The dev file's `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` uses
the `:?` required form, and the value reaches compose only through the Makefile's
`-include web-app/apps/internal-portal/.env.local` plus `.EXPORT_ALL_VARIABLES:`
(`Makefile:25-26`). Run it through `make`, or supply the variable:

```bash
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_parse_only \
docker compose -f docker-compose.dev.yml config -q
```

Then, if a dev stack is convenient to start, `make docker-run` and confirm 3000,
3002 and 8100 all answer.

- [ ] **Step 8: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(ws2): document make deploy-check and what it cannot prove

Records the ALLOWED_ORIGINS constraint too: it gates both CORS and the Clerk
azp check, the browser calls the API cross-origin, and a missing entry
presents as broken auth rather than as a config error."
```

---

## Definition of done

The seven acceptance criteria from the spec, and where each is met:

| # | Criterion | Where |
|---|---|---|
| 1 | Parses with `APP_ENV=staging` and `server/.env.staging` present | Task 3 step 3 (`==> 1/5`) |
| 2 | Both portal images build with their own `APP_NAME`, distinct images | Task 3 steps 3-4 (`==> 3/5`) |
| 3 | Stack comes up: `migrate` exits 0, then `server` reaches healthy | Task 3 step 3 (`==> 4/5`) |
| 4 | A broken migration fails the stack | Task 5 step 2 |
| 5 | No application container publishes to the host | Task 3 step 3 (`==> 5/5`) |
| 6 | Every label reviewed against the Dokploy reference | Task 4 step 7 |
| 7 | `make docker-run` unchanged, still 3000 / 3002 / 8100 | Task 5 step 7 |

Not done, and not in scope: the labels are unexercised, no browser or Clerk or CORS path is touched, no TLS, no Dokploy. Those are the follow-on's, on a VPS.
