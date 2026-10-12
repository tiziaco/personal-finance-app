---
name: run-stack
description: Running this checkout's dev stack natively (VS Code Dev tasks, host processes, Postgres in Docker) or fully in Docker Compose — first-run env files, the ngrok tunnel for Clerk webhooks, and where migrations run on each path. Use when starting, stopping or tunnelling the app, copying env files on a fresh clone, or when the dev servers start but the database schema is behind.
---

# Running the stack

The two paths are mutually exclusive per checkout — root `CLAUDE.md` says why. `make help` (root) and `make -C server help` list every target.

## First run

Each service has its own env file. Copy the examples and fill in values:

```bash
cp .env.example .env   # required by the root Makefile (APP_ENV, GRAFANA_ADMIN_PASSWORD, etc.)
cp server/.env.example server/.env.development
cp web-app/apps/web/.env.example web-app/apps/web/.env.local
```

## Native dev

```bash
make dev-preflight      # verify this checkout's API and web app ports are free
make dev-tunnel         # ngrok: https://$NGROK_DOMAIN -> localhost:$API_HOST_PORT
```

`NGROK_DOMAIN` and `NGROK_AUTHTOKEN` come from the root `.env` (loaded by the Makefile via `-include`), not from your shell — so run the target rather than `ngrok` directly. It passes `--authtoken` explicitly, for the reason in [`docs/setup/clerk.md`](../../../docs/setup/clerk.md) §6.

In VS Code, `Dev: All` (⇧⌘B) chains preflight → start db → migrate → API server and web app. `Dev: All + Tunnel` adds the tunnel, for Clerk webhook work. Migrations are **not** applied automatically on this path the way the Docker `migrate` service does it — `Dev: Migrate` runs `make migrate ENV=development` on the host, **from `server/`** (the task sets `cwd`). The root Makefile has no `migrate` target: by hand it is `make -C server migrate ENV=development`, or `make docker-migrate` for the container route.

## Docker

The root `Makefile` manages the full Compose stack: `make docker-run` (full, with monitoring and ngrok) or `make docker-run-core` (web, server, db). Migrations apply automatically on `docker-run*`; `make docker-migrate` is for on-demand use.

`ngrok` (dev only) tunnels `server:8000` for Clerk webhook delivery. Compose publishes no host port for it, so its inspection dashboard has no fixed URL.

### After a PostgreSQL major-version bump

A data directory from an older major version will not start. Drop the volume and re-apply
migrations — dev users come back through JIT provisioning on the next sign-in:

```bash
make docker-stop
docker volume ls | grep postgres-data      # <project>_postgres-data
docker volume rm <project>_postgres-data
make docker-run-db ENV=development && make -C server migrate ENV=development
```

A linked worktree's volume goes with `make worktree-clean`.
