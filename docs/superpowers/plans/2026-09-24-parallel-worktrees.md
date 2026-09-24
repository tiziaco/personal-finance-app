# Parallel Worktree Stacks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let each linked git worktree run its own dev stack — database, containers, ports — via `make worktree-new` / `worktree-init` / `worktree-clean`.

**Architecture:** A worktree gets a slot N (1–9), saved once in its root `.env`; every host port is the main checkout's base + 10·N, and its Compose project is `<main's project>-<worktree dir>`. Bash scripts under `scripts/worktree/` write the slot's values into the worktree's gitignored env files; the Makefile, Compose file, `package.json`s and VS Code tasks read ports from variables instead of literals. A port of flyorbit PRs #11 and #12, adapted for two portals and a derived project prefix.

**Tech Stack:** bash (macOS + GNU portable), GNU make, Docker Compose v2+ (`DOCKER_COMPOSE ?= docker-compose`), git worktrees, pnpm, uv, Next.js `next dev`.

**Spec:** `docs/superpowers/specs/2026-09-24-parallel-worktrees-design.md`

## Global Constraints

- Slot N ports: internal `base+10N`, supplier `base+10N`, API `base+10N`, Postgres `base+10N`; `STEP=10`, `MAX_SLOT=9`.
- Bases come from the **main checkout's** root `.env` keys `INTERNAL_PORTAL_HOST_PORT`, `SUPPLIER_PORTAL_HOST_PORT`, `API_HOST_PORT`, `POSTGRES_HOST_PORT`; defaults `3000`, `3002`, `8100`, `5434`.
- Worktree Compose project: `<prefix>-<normalised worktree dir name>`; prefix = main's `COMPOSE_PROJECT_NAME`, else main's directory name; normalisation is Compose's: lowercase, drop chars outside `[a-z0-9_-]`, trim leading `-`/`_`.
- Worktrees live at `<main>/.claude/worktrees/<name>`; `NAME` matches `^[a-z0-9][a-z0-9-]*$`; `BRANCH` defaults to `feat/<name>`.
- No `container_name` in `docker-compose.dev.yml`. Never `docker builder prune` from worktree tooling.
- Dependencies install with `uv sync --frozen` and `pnpm install --frozen-lockfile`.
- Scripts: `#!/usr/bin/env bash`, `set -euo pipefail`, no `sed -i`, no `mapfile`. Must pass `bash -n`.
- No server or web **application** code changes; `make check-contract` must stay clean.
- Comments state the constraint and cut the narrative (repo preference).
- Makefile recipe lines are **tab**-indented. Shell `for` loops inside recipes use `$$`.
- The root Makefile exports everything it includes (`.EXPORT_ALL_VARIABLES`); scripts that need ports read them from the environment make provides.

## Review Focus

1. **A free slot's port is held by an unrelated process** → that slot is skipped with a printed reason and the next is taken. *(Task 5, Step 9)*
2. **`make worktree-clean` run twice, or on a stack never started** → succeeds, removes nothing it doesn't own, no error. *(Task 5, Step 13)*
3. **An env file with no trailing newline, or a key written `export KEY=`** → `upsert` replaces in place / appends on its own line; `read_key` returns empty, not failure, for an absent key under `pipefail`. *(Task 5, Step 2)*
4. **A worktree created outside `worktree-new` with an awkward directory name** (`Wt_Odd.x`) → Compose-normalised project name; `init` and `clean` agree on it. *(Task 5, Step 11)*
5. **The main checkout on a non-default block** → a new worktree follows it; re-running `worktree-init` in an existing worktree after main moves carries it along. *(Task 9, Steps 4–5)*

---

## Task 1: Docker entrypoint no longer requires `OPENAI_API_KEY`

**Files:**
- Modify: `server/scripts/docker-entrypoint.sh:51-60`

**Interfaces:** none.

- [ ] **Step 1: Show the current requirement**

Run: `grep -n 'REQUIRED_ENV_VARS-' server/scripts/docker-entrypoint.sh`
Expected: two lines containing `OPENAI_API_KEY,CLERK_WEBHOOK_SIGNING_SECRET`.

- [ ] **Step 2: Edit**

Replace

```bash
required_vars=()
if [[ -n "${REQUIRED_ENV_VARS-OPENAI_API_KEY,CLERK_WEBHOOK_SIGNING_SECRET}" ]]; then
    IFS=',' read -r -a required_vars <<<"${REQUIRED_ENV_VARS-OPENAI_API_KEY,CLERK_WEBHOOK_SIGNING_SECRET}"
fi
```

with

```bash
# OPENAI_API_KEY is deliberately not in the default: config.py defaults it to
# empty and only an LLM call needs it, so requiring it made the container
# stricter than the native server.
required_vars=()
if [[ -n "${REQUIRED_ENV_VARS-CLERK_WEBHOOK_SIGNING_SECRET}" ]]; then
    IFS=',' read -r -a required_vars <<<"${REQUIRED_ENV_VARS-CLERK_WEBHOOK_SIGNING_SECRET}"
fi
```

- [ ] **Step 3: Verify**

Run: `bash -n server/scripts/docker-entrypoint.sh && grep -c OPENAI_API_KEY, server/scripts/docker-entrypoint.sh`
Expected: `0` (no syntax error, no remaining default containing the key). The Docker proof comes in Task 8.

- [ ] **Step 4: Commit**

```bash
git add server/scripts/docker-entrypoint.sh
git commit -m "fix(server): docker entrypoint no longer requires OPENAI_API_KEY"
```

---

## Task 2: `ALLOWED_ORIGINS` example lists the supplier portal

**Files:**
- Modify: `server/.env.example:9`

**Interfaces:** none.

- [ ] **Step 1: Show the gap**

Run: `grep -n ALLOWED_ORIGINS server/.env.example`
Expected: `9:ALLOWED_ORIGINS='["http://localhost:3000", "http://localhost:8100"]'` — no 3002.

- [ ] **Step 2: Edit line 9 to**

```
ALLOWED_ORIGINS='["http://localhost:3000", "http://localhost:3002", "http://localhost:8100"]'
```

- [ ] **Step 3: Verify it parses as the server will read it**

Run: `cd server && set -a && . ./.env.example && set +a && python3 -c 'import json,os; print(json.loads(os.environ["ALLOWED_ORIGINS"]))'`
Expected: `['http://localhost:3000', 'http://localhost:3002', 'http://localhost:8100']`

- [ ] **Step 4: Commit**

```bash
git add server/.env.example
git commit -m "fix(server): ALLOWED_ORIGINS example lists the supplier portal"
```

---

## Task 3: Host ports come from variables

Main's behaviour must not change: with no new keys in `.env`, everything still runs on 3000 / 3002 / 8100 / 5434.

**Files:**
- Modify: `Makefile` (variables near line 13, `.PHONY`, `help`, `dev-preflight`, new `dev-internal` / `dev-supplier` / `dev-kill`, `docker-run` and `docker-run-core` echoes)
- Modify: `server/Makefile:22-25`
- Modify: `docker-compose.dev.yml` (both portals' `ports:`)
- Modify: `web-app/apps/internal-portal/package.json:6`, `web-app/apps/supplier-portal/package.json:6`
- Modify: `.vscode/tasks.json`
- Modify: `.env.example`

**Interfaces:**
- Produces: make variables `INTERNAL_PORTAL_HOST_PORT` (default 3000), `SUPPLIER_PORTAL_HOST_PORT` (default 3002); make targets `dev-internal`, `dev-supplier`, `dev-kill`; Compose reads the same two variable names. Tasks 5 and 8 rely on these exact names.

- [ ] **Step 1: Failing checks**

`timeout` is not installed on this machine. Define this helper in the shell first; Step 11 reuses it:

```bash
port_of() { # port_of <cmd...> — start a dev server, print the port it announces, stop it
  local log pid port
  log="$(mktemp)"; "$@" > "$log" 2>&1 & pid=$!
  for _ in $(seq 1 40); do grep -q 'localhost:[0-9]' "$log" && break; sleep 1; done
  port="$(grep -m1 -o 'localhost:[0-9]*' "$log" | cut -d: -f2)"; echo "localhost:$port"
  lsof -ti ":$port" -sTCP:LISTEN | xargs kill 2>/dev/null; kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null
}
```

Run: `make dev-internal; make dev-kill; (cd web-app && PORT=3993 port_of pnpm dev:supplier)`
Expected: `No rule to make target 'dev-internal'`, `No rule to make target 'dev-kill'`, and `localhost:3002` (the `--port 3002` flag beats `PORT`).

- [ ] **Step 2: Root `Makefile` variables** — after the `API_HOST_PORT ?= 8100` line add:

```make
# Host ports for the two portals, on both paths: compose publishes them, and
# dev-internal / dev-supplier hand them to `next dev` as PORT.
INTERNAL_PORTAL_HOST_PORT ?= 3000
SUPPLIER_PORTAL_HOST_PORT ?= 3002
```

and add `dev-internal dev-supplier dev-kill` to `.PHONY` after `dev-preflight`.

- [ ] **Step 3: `help`** — replace the `dev-preflight` help line with:

```make
	@echo "  make dev-preflight      - Check ports $(API_HOST_PORT)/$(INTERNAL_PORTAL_HOST_PORT)/$(SUPPLIER_PORTAL_HOST_PORT) are free"
	@echo "  make dev-internal       - Internal portal (next dev) on port $(INTERNAL_PORTAL_HOST_PORT)"
	@echo "  make dev-supplier       - Supplier portal (next dev) on port $(SUPPLIER_PORTAL_HOST_PORT)"
	@echo "  make dev-kill           - Kill whatever listens on $(API_HOST_PORT), $(INTERNAL_PORTAL_HOST_PORT), $(SUPPLIER_PORTAL_HOST_PORT) and 4040"
```

- [ ] **Step 4: `dev-preflight` and the new targets** — replace the whole `dev-preflight` target with:

```make
dev-preflight:
	@for port in $(API_HOST_PORT) $(INTERNAL_PORTAL_HOST_PORT) $(SUPPLIER_PORTAL_HOST_PORT); do \
		pids=$$(lsof -ti :$$port -sTCP:LISTEN 2>/dev/null); \
		if [ -n "$$pids" ]; then \
			echo "❌ Port $$port is already in use (PIDs: $$pids)."; \
			echo "   The Docker stack publishes $(INTERNAL_PORTAL_HOST_PORT), $(SUPPLIER_PORTAL_HOST_PORT) and $(API_HOST_PORT) — run 'make docker-stop',"; \
			echo "   or 'make dev-kill' if a previous native run is still alive."; \
			exit 1; \
		fi; \
	done
	@echo "✅ Ports $(API_HOST_PORT), $(INTERNAL_PORTAL_HOST_PORT), $(SUPPLIER_PORTAL_HOST_PORT) are free"

# Through make rather than `pnpm dev:*` directly: only the Makefile has read
# the root .env that says which ports this checkout owns.
dev-internal:
	@cd web-app && PORT=$(INTERNAL_PORTAL_HOST_PORT) pnpm dev:internal

dev-supplier:
	@cd web-app && PORT=$(SUPPLIER_PORTAL_HOST_PORT) pnpm dev:supplier

# 4040 is dev-tunnel's ngrok inspector.
dev-kill:
	@for port in $(API_HOST_PORT) $(INTERNAL_PORTAL_HOST_PORT) $(SUPPLIER_PORTAL_HOST_PORT) 4040; do \
		pids=$$(lsof -ti :$$port -sTCP:LISTEN 2>/dev/null); \
		if [ -n "$$pids" ]; then \
			echo "Killing port $$port (PIDs: $$pids)"; \
			echo "$$pids" | xargs kill -9; \
		else \
			echo "Port $$port: nothing running"; \
		fi; \
	done
```

- [ ] **Step 5: `docker-run` / `docker-run-core` echoes** — in both targets replace

```make
	@echo "   Internal Portal:     http://localhost:3000"
	@echo "   Supplier Portal:     http://localhost:3002"
```

with

```make
	@echo "   Internal Portal:     http://localhost:$(INTERNAL_PORTAL_HOST_PORT)"
	@echo "   Supplier Portal:     http://localhost:$(SUPPLIER_PORTAL_HOST_PORT)"
```

- [ ] **Step 6: `server/Makefile`** — replace

```make
# Host port for the native (non-Docker) server. 8000 collides with other
# projects on the same machine; keep this in step with API_HOST_PORT in the
# root Makefile, which publishes the same port from the container.
PORT ?= 8100
```

with

```make
# Host port for the native (non-Docker) server. Follows API_HOST_PORT from the
# root .env (included above), the variable compose publishes the container on.
API_HOST_PORT ?= 8100
PORT ?= $(API_HOST_PORT)
```

- [ ] **Step 7: `docker-compose.dev.yml`** — `internal-portal` `ports:` becomes `- "${INTERNAL_PORTAL_HOST_PORT:-3000}:3000"`; `supplier-portal` `ports:` becomes `- "${SUPPLIER_PORTAL_HOST_PORT:-3002}:3000"`.

- [ ] **Step 8: Portal `package.json`s** — `internal-portal`: `"dev": "next dev --port ${PORT:-3000}",`; `supplier-portal`: `"dev": "next dev --port ${PORT:-3002}",`.

- [ ] **Step 9: `.vscode/tasks.json`**
  - Header comment lines 6–8 become:
    ```jsonc
    // The Dev chain and the Run chain are mutually exclusive. Compose publishes
    // the same portal and API ports (3000, 3002 and 8100 in the main checkout),
    // and its `ngrok` service claims the same static domain as "Dev: Tunnel".
    // Stop one before starting the other. Ports come from the root .env via
    // make, so these tasks work unchanged in a worktree opened as its own window.
    ```
  - `Dev: Preflight` detail: `"Fail early if the API or portal ports (8100/3000/3002 in main) are taken"`
  - `Dev: API Server` detail: `"Run FastAPI server locally with hot-reload (port 8100 in main)"`
  - `Dev: Internal Portal`: detail `"Run internal-portal Next.js dev server (port 3000 in main)"`, command `"make dev-internal"`, cwd `"${workspaceFolder}"`
  - `Dev: Supplier Portal`: detail `"Run supplier-portal Next.js dev server (port 3002 in main)"`, command `"make dev-supplier"`, cwd `"${workspaceFolder}"`
  - `Dev: Tunnel` detail: `"ngrok tunnel from the static domain to the API port (Clerk webhooks)"`
  - `Dev: Kill All`: detail `"Kill any process on the API, portal and 4040 (ngrok inspector) ports"`, command `"make dev-kill"`, add `"options": { "cwd": "${workspaceFolder}" },`

- [ ] **Step 10: Root `.env.example`** — after the `APP_ENV` block add:

```
# Host ports this checkout publishes and runs on. The defaults are usually
# right; set them where they collide. Several projects built from this template
# on one machine: give each its own block of 100 (e.g. 3200 / 3202 / 8300), and
# set ALLOWED_ORIGINS (server/.env.development) and NEXT_PUBLIC_API_URL (both
# portals' .env.local) to match.
# INTERNAL_PORTAL_HOST_PORT=3000
# SUPPLIER_PORTAL_HOST_PORT=3002
# API_HOST_PORT=8100
# POSTGRES_HOST_PORT=5434
```

- [ ] **Step 11: Verify — defaults unchanged, overrides honoured**

```bash
make help | grep -E 'dev-(preflight|internal|supplier|kill)'
make dev-preflight
make -C server -n dev | grep -o -- '--port [0-9]*'
API_HOST_PORT=8997 make -C server -n dev | grep -o -- '--port [0-9]*'
(cd web-app && port_of pnpm dev:supplier)
(cd web-app && PORT=3993 port_of pnpm dev:supplier)
SUPPLIER_PORTAL_HOST_PORT=3994 port_of make dev-supplier
set -a; . ./.env; . web-app/apps/internal-portal/.env.local; set +a
INTERNAL_PORTAL_HOST_PORT=3995 docker compose -f docker-compose.dev.yml config | grep -E 'published: "?(3995|3002|8100|5434)'
python3 -c 'import json,re,sys; json.loads(re.sub(r"^\s*//.*$","",open(".vscode/tasks.json").read(),flags=re.M))' && echo tasks.json ok
```

Expected, in order: four help lines showing `8100/3000/3002`; `✅ Ports 8100, 3000, 3002 are free` (if a port is busy, `make dev-kill` then retry); `--port 8100`; `--port 8997`; `localhost:3002`; `localhost:3993`; `localhost:3994`; four `published:` lines for 3995, 3002, 8100, 5434; `tasks.json ok`. Run `make dev-kill` afterwards if anything is left listening.

- [ ] **Step 12: `make check`** — Run: `make check`. Expected: passes (Prettier covers the `package.json`s).

- [ ] **Step 13: Commit**

```bash
git add Makefile server/Makefile docker-compose.dev.yml web-app/apps/internal-portal/package.json web-app/apps/supplier-portal/package.json .vscode/tasks.json .env.example
git commit -m "refactor(dev): host ports come from variables"
```

---

## Task 4: Drop `container_name` from the dev compose file

**Files:**
- Modify: `docker-compose.dev.yml` (six `container_name:` lines, new header comment)
- Modify: `docker-compose.prod.yml:9-11` (comment)
- Modify: `server/scripts/compose-env.sh:3-8` (comment)
- Modify: `server/scripts/docker-image-name.sh:13-16` (comment)
- Modify: `server/CLAUDE.md:37-41`

**Interfaces:** none new. Main's containers become `fullstack-multitenant-next-fastapi-tmp-<service>-1`; the volume stays `fullstack-multitenant-next-fastapi-tmp_postgres-data`.

- [ ] **Step 1: Snapshot main's database under the old names**

```bash
make docker-run-db ENV=development
DB=$(docker ps -q -f label=com.docker.compose.project=fullstack-multitenant-next-fastapi-tmp -f label=com.docker.compose.service=db)
docker inspect -f '{{.Name}} {{range .Mounts}}{{.Name}}{{end}}' "$DB"
docker exec "$DB" sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --data-only' | shasum > "$TMPDIR/db-before.sha"
(cd server && uv run alembic current 2>/dev/null | tail -1) | tee "$TMPDIR/alembic-before.txt"
make docker-stop
```

Expected: `/db fullstack-multitenant-next-fastapi-tmp_postgres-data`, then a revision id.

- [ ] **Step 2: Failing check** — Run: `grep -c container_name docker-compose.dev.yml`. Expected: `6`.

- [ ] **Step 3: Edit `docker-compose.dev.yml`** — delete all six `container_name:` lines and insert above `services:`:

```yaml
# No container_name anywhere: a container name is host-global, and every git
# worktree runs its own copy of this stack under its own COMPOSE_PROJECT_NAME
# (`make worktree-init`). Service DNS (`db`, `server:8000`) is per-project
# network, so it is unaffected. Same rule as docker-compose.prod.yml.
```

- [ ] **Step 4: Comments that described the old pin**
  - `docker-compose.prod.yml`: replace `# docker-compose.dev.yml keeps its names — one stack per laptop.` with `# docker-compose.dev.yml follows the same rule, for its per-worktree stacks.`
  - `server/scripts/compose-env.sh`: replace the sentences from `The container` through `wrong` / `for one of the two files.` with:
    ```bash
    # Defines compose(), which addresses the stack by *service* name. The container
    # name is Compose's to choose (<project>-server-1, and the project differs per
    # git worktree), so naming it here would copy a value this script does not own.
    ```
    keeping the following `PROJECT_NAME is unrelated…` sentence.
  - `server/scripts/docker-image-name.sh`: replace `and logs-docker.sh address \`container_name: server\` instead.` with `and logs-docker.sh address the Compose service \`server\` instead.`
  - `server/CLAUDE.md`: replace `` — `docker-compose.dev.yml` pins `container_name: server` while the prod file does not, so the name is Compose's to resolve. `` with `` — neither compose file pins one, and in a git worktree the project, and with it the container name, differs. ``

- [ ] **Step 5: Verify — same volume, same data**

```bash
grep -rn --exclude-dir=.venv 'container_name: server' server/ docker-compose.*.yml; echo "refs: $?"
make docker-run-db ENV=development
DB=$(docker ps -q -f label=com.docker.compose.project=fullstack-multitenant-next-fastapi-tmp -f label=com.docker.compose.service=db)
docker inspect -f '{{.Name}} {{range .Mounts}}{{.Name}}{{end}}' "$DB"
docker exec "$DB" sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --data-only' | shasum | diff - "$TMPDIR/db-before.sha" && echo data unchanged
(cd server && uv run alembic current 2>/dev/null | tail -1) | diff - "$TMPDIR/alembic-before.txt" && echo head unchanged
docker ps -a --format '{{.Names}}' | grep -x db; echo "old name gone: $?"
```

Expected: `refs: 1`; `/fullstack-multitenant-next-fastapi-tmp-db-1 fullstack-multitenant-next-fastapi-tmp_postgres-data`; `data unchanged`; `head unchanged`; `old name gone: 1`. Leave the database running.

- [ ] **Step 6: Commit**

```bash
git add docker-compose.dev.yml docker-compose.prod.yml server/scripts/compose-env.sh server/scripts/docker-image-name.sh server/CLAUDE.md
git commit -m "refactor(dev): drop container_name from the dev compose file"
```

---

## Task 5: Parallel worktree stacks — `worktree-init`, `worktree-clean`

**Files:**
- Create: `scripts/lib/env.sh`, `scripts/worktree/lib.sh`, `scripts/worktree/init.sh`, `scripts/worktree/clean.sh`
- Modify: `Makefile` (`WORKTREE_SLOT`, `.PHONY`, `help`, two targets, `docker-run` guard)
- Modify: `.env.example`, `.gitignore`

**Interfaces:**
- Produces (`scripts/lib/env.sh`): `upsert <file> <key> <value>` — replace or append `key=value`; `read_key <file> <key>` — prints the last value, surrounding quotes stripped, empty if absent, always exit 0.
- Produces (`scripts/worktree/lib.sh`, sources `env.sh`): `main_checkout` — prints main's absolute path; `is_main_checkout` — exit 0 in main; `normalize_project_name <s>` — Compose's rule; `project_prefix` — normalised main `COMPOSE_PROJECT_NAME` or main dir name. Task 6 sources this file for `main_checkout`.
- Produces: `make worktree-init`, `make worktree-clean`; root `.env` keys `WORKTREE_SLOT`, `COMPOSE_PROJECT_NAME`.
- Consumes: Task 3's variable names.

- [ ] **Step 1: Write the helper test (fails: files absent)** — save as `$TMPDIR/test-worktree-lib.sh`, not committed:

```bash
#!/usr/bin/env bash
set -euo pipefail
REPO="${1:?repo root}"
source "$REPO/scripts/worktree/lib.sh"
fail=0
check() { if [ "$2" = "$3" ]; then echo "ok   $1"; else echo "FAIL $1: got [$2] want [$3]"; fail=1; fi; }
d="$(mktemp -d)"

printf 'A=1\n# B=commented\nexport B=2\nC=3' > "$d/f"          # no trailing newline
upsert "$d/f" B 20; upsert "$d/f" D 4; upsert "$d/f" A 1
check "upsert result" "$(cat "$d/f")" "$(printf 'A=1\n# B=commented\nB=20\nC=3\nD=4')"
printf 'X=1' > "$d/n"                                         # append path, no trailing newline
upsert "$d/n" Y 2
check "upsert append after no newline" "$(cat "$d/n")" "$(printf 'X=1\nY=2')"
check "read_key plain" "$(read_key "$d/f" D)" "4"
check "read_key absent" "$(read_key "$d/f" NOPE)" ""
check "read_key no file" "$(read_key "$d/missing" A)" ""
printf "Q='[\"x\", \"y\"]'\nR=\"v\"\n" > "$d/q"
check "read_key strips outer quotes" "$(read_key "$d/q" Q)" '["x", "y"]'
check "read_key double quotes" "$(read_key "$d/q" R)" "v"
check "normalize" "$(normalize_project_name 'Wt_Odd.x')" "wt_oddx"
check "normalize leading" "$(normalize_project_name '-_My Proj')" "myproj"
check "main_checkout" "$(cd "$REPO" && main_checkout)" "$(cd "$REPO" && pwd -P)"
if (cd "$REPO" && is_main_checkout); then r=yes; else r=no; fi
check "is_main_checkout in main" "$r" yes
rm -rf "$d"; exit $fail
```

Run: `bash "$TMPDIR/test-worktree-lib.sh" "$PWD"`. Expected: fails — `scripts/worktree/lib.sh: No such file or directory`.

- [ ] **Step 2: Create `scripts/lib/env.sh`**

```bash
#!/usr/bin/env bash
# Env-file helpers. Sourced, never executed. Callers write into gitignored env
# files and must leave comments, ordering and unrelated keys alone.
#
#     source "$(dirname "${BASH_SOURCE[0]}")/../lib/env.sh"

# Replace a key in place, or append it. awk to a temp file rather than
# `sed -i`, whose syntax differs between BSD (macOS) and GNU.
upsert() { # upsert <file> <key> <value>
  local file=$1 key=$2 line="$2=$3"
  if grep -qE "^[[:space:]]*(export[[:space:]]+)?${key}=" "$file" 2>/dev/null; then
    awk -v key="$key" -v line="$line" '
      $0 ~ "^[[:space:]]*(export[[:space:]]+)?" key "=" { print line; next }
      { print }
    ' "$file" > "$file.tmp" && mv "$file.tmp" "$file"
  else
    # Without a trailing newline the new key would be glued onto the last one.
    [ -s "$file" ] && [ -n "$(tail -c 1 "$file")" ] && printf '\n' >> "$file"
    printf '%s\n' "$line" >> "$file"
  fi
}

# The last value of <key> in <file>, outer quotes stripped; empty if the file
# or key is absent.
read_key() { # read_key <file> <key>
  [ -f "$1" ] || return 0
  # `|| true`: under pipefail an absent key would fail the caller's assignment.
  { grep -E "^[[:space:]]*(export[[:space:]]+)?$2=" "$1" || true; } | tail -n 1 \
    | cut -d= -f2- | sed -e "s/^[\"']//" -e "s/[\"']$//"
}
```

- [ ] **Step 3: Create `scripts/worktree/lib.sh`**

```bash
#!/usr/bin/env bash
# Helpers shared by scripts/worktree/*. Sourced, never executed.

# shellcheck source=../lib/env.sh
source "$(dirname "${BASH_SOURCE[0]}")/../lib/env.sh"

# The first entry of `git worktree list` is always the main checkout.
main_checkout() {
  git worktree list --porcelain | awk '/^worktree /{ print substr($0, 10); exit }'
}

# Only the main checkout's git dir is the common dir.
is_main_checkout() {
  [ "$(git rev-parse --path-format=absolute --git-dir)" = \
    "$(git rev-parse --path-format=absolute --git-common-dir)" ]
}

# Compose's own rule, so an unset name matches the project Compose runs.
normalize_project_name() { # normalize_project_name <name>
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | sed -e 's/[^a-z0-9_-]//g' -e 's/^[-_]*//'
}

# Main's COMPOSE_PROJECT_NAME, else its directory name. Derived rather than
# fixed, so a fork needs no setting and an existing volume keeps its name.
project_prefix() {
  local main name
  main="$(main_checkout)"
  name="$(read_key "$main/.env" COMPOSE_PROJECT_NAME)"
  normalize_project_name "${name:-$(basename "$main")}"
}
```

- [ ] **Step 4: Run the helper test** — Run: `bash "$TMPDIR/test-worktree-lib.sh" "$PWD"`. Expected: every line `ok`, exit 0.

- [ ] **Step 5: Create `scripts/worktree/init.sh`** (then `chmod +x`)

```bash
#!/usr/bin/env bash
# Give a linked git worktree its own dev stack: a slot, a compose project, a
# port set, the env files, and installed dependencies.
#
# Slot N owns base + 10N for each host port. Bases are the main checkout's (its
# root .env, else 3000/3002/8100/5434), so a re-run after main moves to another
# block of 100 moves this worktree too. Main is slot 0 and never runs this.
#
# The slot is allocated once and saved as WORKTREE_SLOT: recomputing it per run
# would move every URL the day something else held a port.
#
# Values are written into the files, not derived at runtime. set_env.sh sources
# server/.env.development with `set -a`, so its POSTGRES_PORT beats anything
# exported; and ALLOWED_ORIGINS gates Clerk's azp check, so a missing origin
# looks like broken auth.
#
# Idempotent.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/../.."

# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

STEP=10
# Slot 10 would reach the next project's block of 100.
MAX_SLOT=9

if is_main_checkout; then
  echo "FAIL: this is the main checkout. It is slot 0 and needs no init."
  echo "Create a worktree with: make worktree-new NAME=<name>"
  exit 1
fi

HERE="$(pwd -P)"
MAIN="$(main_checkout)"

worktrees() { git worktree list --porcelain | awk '/^worktree /{ print substr($0, 10) }'; }
is_here() { [ "$(cd "$1" 2>/dev/null && pwd -P)" = "$HERE" ]; }
port_busy() { lsof -ti ":$1" -sTCP:LISTEN > /dev/null 2>&1; }

# ── Env files ────────────────────────────────────────────────────────────────
# Copied only when missing, so a re-run never clobbers a hand edit.
echo "==> Env files"
for f in .env server/.env.development \
         web-app/apps/internal-portal/.env.local web-app/apps/supplier-portal/.env.local \
         server/.env.test; do
  if [ -f "$f" ]; then
    echo "    $f (kept)"
  elif [ -f "$MAIN/$f" ]; then
    cp "$MAIN/$f" "$f"
    echo "    $f (copied from $MAIN)"
  elif [ "$f" = server/.env.test ]; then
    # Optional: only `make test` reads it, against a testcontainer.
    echo "    $f (absent in the main checkout too; skipped)"
  else
    echo "FAIL: $MAIN/$f does not exist. Set up the main checkout first"
    echo "(see 'Environment Setup' in CLAUDE.md), then re-run this."
    exit 1
  fi
done

# ── Bases ────────────────────────────────────────────────────────────────────
base_port() { # base_port <key> <default>
  local v
  v="$(read_key "$MAIN/.env" "$1")"
  v="${v:-$2}"
  if ! [[ "$v" =~ ^[0-9]+$ ]]; then
    echo "FAIL: $1=$v in $MAIN/.env is not a port number." >&2
    exit 1
  fi
  echo "$v"
}
BASE_INTERNAL="$(base_port INTERNAL_PORTAL_HOST_PORT 3000)"
BASE_SUPPLIER="$(base_port SUPPLIER_PORTAL_HOST_PORT 3002)"
BASE_API="$(base_port API_HOST_PORT 8100)"
BASE_DB="$(base_port POSTGRES_HOST_PORT 5434)"

slot_ports() { # slot_ports <n> -> "internal supplier api db"
  echo $((BASE_INTERNAL + STEP * $1)) $((BASE_SUPPLIER + STEP * $1)) \
       $((BASE_API + STEP * $1)) $((BASE_DB + STEP * $1))
}

# ── Slot ─────────────────────────────────────────────────────────────────────
SLOT="$(read_key .env WORKTREE_SLOT)"
if [ -n "$SLOT" ]; then
  if ! [[ "$SLOT" =~ ^[1-9]$ ]]; then
    echo "FAIL: WORKTREE_SLOT=$SLOT in .env is not a slot between 1 and $MAX_SLOT."
    exit 1
  fi
  echo "==> Slot $SLOT (already assigned)"
else
  taken=" "
  while IFS= read -r path; do
    is_here "$path" && continue
    taken+="$(read_key "$path/.env" WORKTREE_SLOT) "
  done < <(worktrees)

  for n in $(seq 1 "$MAX_SLOT"); do
    case "$taken" in *" $n "*) continue ;; esac
    busy=""
    for p in $(slot_ports "$n"); do
      if port_busy "$p"; then busy+=" $p"; fi
    done
    if [ -n "$busy" ]; then
      echo "    slot $n skipped: port(s)$busy already in use by something else"
      continue
    fi
    SLOT=$n
    break
  done

  if [ -z "$SLOT" ]; then
    echo "FAIL: no free slot between 1 and $MAX_SLOT."
    echo "Remove a finished worktree ('make worktree-clean', then 'git worktree remove')."
    exit 1
  fi
  echo "==> Slot $SLOT (newly assigned)"
fi

read -r INTERNAL_PORT SUPPLIER_PORT API_PORT DB_PORT <<< "$(slot_ports "$SLOT")"

# ── Compose project ──────────────────────────────────────────────────────────
NAME="$(normalize_project_name "$(basename "$HERE")")"
PROJECT="$(project_prefix)-${NAME:-slot$SLOT}"

# Two same-named directories in different places would share a database volume.
while IFS= read -r path; do
  is_here "$path" && continue
  if [ "$(read_key "$path/.env" COMPOSE_PROJECT_NAME)" = "$PROJECT" ]; then
    echo "FAIL: $path already uses COMPOSE_PROJECT_NAME=$PROJECT."
    echo "Rename this worktree's directory and re-run."
    exit 1
  fi
done < <(worktrees)

# ── Slot values ──────────────────────────────────────────────────────────────
echo "==> Writing slot $SLOT values"
upsert .env WORKTREE_SLOT "$SLOT"
upsert .env COMPOSE_PROJECT_NAME "$PROJECT"
upsert .env INTERNAL_PORTAL_HOST_PORT "$INTERNAL_PORT"
upsert .env SUPPLIER_PORTAL_HOST_PORT "$SUPPLIER_PORT"
upsert .env API_HOST_PORT "$API_PORT"
upsert .env POSTGRES_HOST_PORT "$DB_PORT"
upsert server/.env.development POSTGRES_PORT "$DB_PORT"
upsert server/.env.development ALLOWED_ORIGINS \
  "'[\"http://localhost:$INTERNAL_PORT\", \"http://localhost:$SUPPLIER_PORT\", \"http://localhost:$API_PORT\"]'"
for f in web-app/apps/internal-portal/.env.local web-app/apps/supplier-portal/.env.local; do
  upsert "$f" NEXT_PUBLIC_API_URL "http://localhost:$API_PORT"
done

# ── Dependencies ─────────────────────────────────────────────────────────────
# Frozen: resolving belongs to whoever changes a dependency. Both tools
# hard-link from a global cache, so a second copy is quick and small.
echo "==> Server dependencies (uv sync)"
(cd server && uv sync --frozen)
echo "==> Web dependencies (pnpm install)"
(cd web-app && pnpm install --frozen-lockfile)

cat <<EOF

✅ Worktree ready — slot $SLOT, compose project $PROJECT

   Internal portal:  http://localhost:$INTERNAL_PORT
   Supplier portal:  http://localhost:$SUPPLIER_PORT
   API server:       http://localhost:$API_PORT   (Swagger: /docs)
   PostgreSQL:       localhost:$DB_PORT

Next, natively (or VS Code 'Dev: All' with this folder open):
   make docker-run-db ENV=development && make -C server migrate ENV=development
   make -C server dev   |   make dev-internal   |   make dev-supplier
Or in Docker:
   make docker-run-core

Monitoring and ngrok stay in the main checkout. Before removing this worktree,
run 'make worktree-clean' so its database volume and images go with it.
EOF
```

- [ ] **Step 6: Create `scripts/worktree/clean.sh`** (then `chmod +x`)

```bash
#!/usr/bin/env bash
# Tear down a worktree's dev stack before the worktree is removed: its native
# dev servers, then its containers, network, volumes and the images it built.
#
# `git worktree remove` deletes only the directory; without this the project's
# volume and images outlive it with nothing naming them. Never `docker builder
# prune` (unlike `make clean`): the build cache is shared with every checkout.
#
# Run through `make worktree-clean`: compose interpolates the whole file even
# for `down`, and the Makefile exports the variables it requires.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/../.."

# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

if is_main_checkout; then
  echo "FAIL: this is the main checkout. Use 'make docker-stop' or 'make clean' here."
  exit 1
fi

PREFIX="$(project_prefix)"
PROJECT="${COMPOSE_PROJECT_NAME:-}"
case "$PROJECT" in
  "$PREFIX"-?*) ;;
  *)
    echo "FAIL: COMPOSE_PROJECT_NAME is '$PROJECT', not a worktree project ($PREFIX-<name>)."
    echo "Was 'make worktree-init' run in this worktree?"
    exit 1
    ;;
esac

HERE="$(pwd -P)"

# A port match is not proof of ownership: only processes whose cwd is inside
# this worktree are stopped. Closing a VS Code terminal does not reliably end
# uvicorn's reloader or next-server, and once the directory is gone nothing
# points at them. 4040 is dev-tunnel's ngrok inspector.
PORTS="${API_HOST_PORT:?} ${INTERNAL_PORTAL_HOST_PORT:?} ${SUPPLIER_PORTAL_HOST_PORT:?} 4040"
echo "🛑 Stopping this worktree's native dev servers (ports $PORTS)..."
pids=()
for port in $PORTS; do
  for pid in $(lsof -ti ":$port" -sTCP:LISTEN 2>/dev/null || true); do
    cwd="$(lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p')"
    case "$cwd" in
      "$HERE" | "$HERE"/*)
        pids+=("$pid")
        echo "    stopping PID $pid on port $port"
        ;;
      *)
        echo "    leaving PID $pid on port $port alone: it runs from ${cwd:-an unknown directory}"
        ;;
    esac
  done
done
if [ ${#pids[@]} -gt 0 ]; then
  # TERM so uvicorn and Next shut down cleanly; KILL what is left after 5 s.
  kill "${pids[@]}" 2>/dev/null || true
  alive=()
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    alive=()
    for pid in "${pids[@]}"; do if kill -0 "$pid" 2>/dev/null; then alive+=("$pid"); fi; done
    [ ${#alive[@]} -eq 0 ] && break
    sleep 0.5
  done
  if [ ${#alive[@]} -gt 0 ]; then
    kill -9 "${alive[@]}" 2>/dev/null || true
    echo "    force-killed: ${alive[*]}"
  fi
else
  echo "    none running"
fi

echo "🧹 Removing compose project $PROJECT (containers, network, volumes)..."
# Unquoted: DOCKER_COMPOSE may be the two-word "docker compose".
# shellcheck disable=SC2086
${DOCKER_COMPOSE:-docker-compose} -p "$PROJECT" -f docker-compose.dev.yml down -v --remove-orphans

# Not `down --rmi all`, which also removes pulled images (pgvector, ngrok) main
# uses. Only the three this project built.
for image in "$PROJECT-server" "$PROJECT-internal-portal" "$PROJECT-supplier-portal"; do
  if docker image inspect "$image" > /dev/null 2>&1; then
    docker image rm "$image" > /dev/null && echo "    removed image $image"
  fi
done

echo "✅ $PROJECT removed. 'git worktree remove' can follow."
```

- [ ] **Step 7: Makefile, `.env.example`, `.gitignore`**
  - `Makefile`, after the portal port variables from Task 3:
    ```make
    # The ports above are slot 0's — the main checkout's. A linked worktree gets
    # slot N from `make worktree-init`, which writes base + 10·N for each (and
    # WORKTREE_SLOT) into that worktree's root .env. Absent means 0.
    WORKTREE_SLOT ?= 0
    ```
  - `.PHONY`: add `worktree-init worktree-clean` after `dev-tunnel`.
  - `help`, after the `dev-tunnel` line and its blank echo:
    ```make
    	@echo "Parallel worktrees (one dev stack per git worktree):"
    	@echo "  make worktree-init      - In a linked worktree: assign a slot, ports, env files, deps"
    	@echo "  make worktree-clean     - In a linked worktree: stop its dev servers, remove its containers, volume, images"
    	@echo ""
    ```
  - Targets, after `dev-tunnel`:
    ```make
    # One stack per linked git worktree, under its own compose project and ports;
    # the slot logic is in scripts/worktree/init.sh.
    worktree-init:
    	@./scripts/worktree/init.sh

    worktree-clean:
    	@./scripts/worktree/clean.sh
    ```
  - `docker-run`: replace the comment `# Full stack - all services including monitoring` with the lines below, and make the guard the first recipe line:
    ```make
    # Full stack - all services including monitoring. Main checkout only:
    # monitoring publishes fixed ports and ngrok claims the one NGROK_DOMAIN.
    docker-run:
    	@if [ "$(WORKTREE_SLOT)" != "0" ]; then \
    		echo "❌ This is worktree slot $(WORKTREE_SLOT). The full stack (monitoring, ngrok) runs"; \
    		echo "   only in the main checkout. Use 'make docker-run-core' here."; \
    		exit 1; \
    	fi
    ```
  - `.env.example`: append to the port block from Task 3 the sentence `# Linked git worktrees follow at base + 10 x slot.` and add after it:
    ```
    # Compose project. Unset, Compose uses this directory's name. Setting it on a
    # checkout that already has data points Compose at a new, empty database
    # volume (<project>_postgres-data). Worktrees use <this>-<worktree dir>.
    # COMPOSE_PROJECT_NAME=

    # Written by `make worktree-init` in a linked worktree, with the ports above.
    # Leave unset in the main checkout (slot 0).
    # WORKTREE_SLOT=
    ```
  - `.gitignore`: under `# Git worktrees`, after `.worktrees`, add `.claude/worktrees/`.

- [ ] **Step 8: Syntax + main-checkout guards, then commit** (a worktree only sees committed scripts)

```bash
chmod +x scripts/worktree/init.sh scripts/worktree/clean.sh
bash -n scripts/lib/env.sh scripts/worktree/lib.sh scripts/worktree/init.sh scripts/worktree/clean.sh && echo syntax ok
command -v shellcheck && shellcheck scripts/lib/env.sh scripts/worktree/*.sh
make worktree-init; echo "exit $?"
make worktree-clean; echo "exit $?"
git add scripts/lib/env.sh scripts/worktree Makefile .env.example .gitignore
git commit -m "feat: parallel worktree stacks (slot + offset)"
```

Expected: `syntax ok`; `FAIL: this is the main checkout. It is slot 0…` / `exit 2` (make reports the script's 1 as 2); `FAIL: this is the main checkout. Use 'make docker-stop'…` / `exit 2`. Failures found in Steps 9–13 are fixed and folded in with `git commit --amend` (the branch is unpushed), then the test worktrees are re-created from the new HEAD.

- [ ] **Step 9: First worktree, plus the busy-port skip (Review Focus 1)**

```bash
git worktree add -b chore/wt-a .claude/worktrees/wt-a
(cd .claude/worktrees/wt-a && make worktree-init) | grep -E '^==> Slot|compose project'
python3 -m http.server 3020 --bind 127.0.0.1 >/dev/null 2>&1 & HOLD=$!
git worktree add -b chore/wt-b .claude/worktrees/wt-b
(cd .claude/worktrees/wt-b && make worktree-init) | grep -E 'skipped|^==> Slot'
kill $HOLD
```

Expected: `==> Slot 1 (newly assigned)` and `slot 1, compose project fullstack-multitenant-next-fastapi-tmp-wt-a`; then `slot 2 skipped: port(s) 3020 already in use by something else` and `==> Slot 3 (newly assigned)`.

- [ ] **Step 10: Keys and idempotency**

```bash
cd .claude/worktrees/wt-a
grep -E '^(WORKTREE_SLOT|COMPOSE_PROJECT_NAME|[A-Z_]+_HOST_PORT)=' .env
grep -E '^(POSTGRES_PORT|ALLOWED_ORIGINS)=' server/.env.development
grep -h NEXT_PUBLIC_API_URL web-app/apps/*/.env.local
make help | grep dev-preflight
F=".env server/.env.development web-app/apps/internal-portal/.env.local web-app/apps/supplier-portal/.env.local"
shasum $F > "$TMPDIR/wt-a.sha"; make worktree-init > /dev/null; shasum -c "$TMPDIR/wt-a.sha"
make docker-run; echo "exit $?"
cd ../../..
```

Expected: `WORKTREE_SLOT=1`, `COMPOSE_PROJECT_NAME=fullstack-multitenant-next-fastapi-tmp-wt-a`, `INTERNAL_PORTAL_HOST_PORT=3010`, `SUPPLIER_PORTAL_HOST_PORT=3012`, `API_HOST_PORT=8110`, `POSTGRES_HOST_PORT=5444`; `POSTGRES_PORT=5444`, `ALLOWED_ORIGINS='["http://localhost:3010", "http://localhost:3012", "http://localhost:8110"]'`; two `NEXT_PUBLIC_API_URL=http://localhost:8110`; help shows `8110/3010/3012`; four `: OK`; `❌ This is worktree slot 1…` and `exit 2`.

- [ ] **Step 11: Awkward directory name (Review Focus 4)**

```bash
git worktree add -b chore/wt-odd .claude/worktrees/Wt_Odd.x
(cd .claude/worktrees/Wt_Odd.x && make worktree-init | grep 'compose project' && make worktree-clean | tail -1)
git worktree remove --force .claude/worktrees/Wt_Odd.x && git branch -D chore/wt-odd
```

Expected: `compose project fullstack-multitenant-next-fastapi-tmp-wt_oddx`; `✅ fullstack-multitenant-next-fastapi-tmp-wt_oddx removed.`

- [ ] **Step 12: Clean stops only this worktree's processes**

```bash
cd .claude/worktrees/wt-a
make docker-run-db ENV=development
python3 -m http.server 3010 --bind 127.0.0.1 >/dev/null 2>&1 & MINE=$!
(cd / && python3 -m http.server 8110 --bind 127.0.0.1 >/dev/null 2>&1 & echo $! > "$TMPDIR/foreign.pid")
sleep 1; make worktree-clean
kill -0 $MINE 2>/dev/null; echo "mine alive: $?"
kill -0 "$(cat "$TMPDIR/foreign.pid")"; echo "foreign alive: $?"; kill "$(cat "$TMPDIR/foreign.pid")"
docker volume ls -q | grep wt-a; echo "volume gone: $?"
docker volume ls -q | grep -x fullstack-multitenant-next-fastapi-tmp_postgres-data
cd ../../..
```

Expected: `stopping PID … on port 3010`, `leaving PID … on port 8110 alone: it runs from /`; `mine alive: 1`; `foreign alive: 0`; `volume gone: 1`; main's volume still listed.

- [ ] **Step 13: Clean is safe to repeat (Review Focus 2), then tear down**

```bash
(cd .claude/worktrees/wt-a && make worktree-clean; echo "exit $?")
(cd .claude/worktrees/wt-b && make worktree-clean > /dev/null; echo "exit $?")
git worktree remove .claude/worktrees/wt-a && git worktree remove .claude/worktrees/wt-b
git branch -D chore/wt-a chore/wt-b && git worktree list
```

Expected: `none running`, no error, `exit 0` twice; `git worktree list` shows only the main checkout.

- [ ] **Step 14: `make check`** — Expected: passes.

---

## Task 6: `make worktree-new`

**Files:**
- Create: `scripts/worktree/new.sh`
- Modify: `Makefile` (`.PHONY`, `help`, target), `scripts/worktree/init.sh` (its main-checkout FAIL message already points at `worktree-new`; no change needed — verify)

**Interfaces:**
- Consumes: `main_checkout` from `scripts/worktree/lib.sh`; each worktree's own `scripts/worktree/init.sh`.
- Produces: `make worktree-new NAME=<name> [BRANCH=<branch>]`.

- [ ] **Step 1: Failing check** — Run: `make worktree-new NAME=x`. Expected: `No rule to make target 'worktree-new'`.

- [ ] **Step 2: Create `scripts/worktree/new.sh`** (then `chmod +x`)

```bash
#!/usr/bin/env bash
# Create a linked worktree under <main>/.claude/worktrees/<name> and give it
# its dev stack: `git worktree add`, then that worktree's own init.sh.
#
#     new.sh <name> [branch]      # branch defaults to feat/<name>
#
# Branch: an existing local branch is checked out; else origin/<branch> is
# tracked (a PR branch); else a new branch starts from the current HEAD.
#
# Why not `claude --worktree`: it names the branch worktree-<name>, bases it on
# origin's default branch, starts before init has run, and on a clean exit
# removes the directory without worktree-clean, stranding the slot's volume and
# images.
#
# NAME is limited to lowercase letters, digits and '-': it becomes part of the
# compose project name, which should match what was typed.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

NAME="${1:-}"
BRANCH="${2:-}"

if [ -z "$NAME" ]; then
  echo "Usage: make worktree-new NAME=<name> [BRANCH=<branch>]   (branch defaults to feat/<name>)"
  exit 1
fi
if ! [[ "$NAME" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
  echo "FAIL: NAME='$NAME'. Use lowercase letters, digits and '-' (it becomes the compose project name)."
  exit 1
fi
BRANCH="${BRANCH:-feat/$NAME}"
if ! git check-ref-format --branch "$BRANCH" > /dev/null 2>&1; then
  echo "FAIL: BRANCH='$BRANCH' is not a valid branch name."
  exit 1
fi

DIR="$(main_checkout)/.claude/worktrees/$NAME"
if [ -e "$DIR" ]; then
  echo "FAIL: $DIR already exists. Pick another NAME, or remove that worktree first"
  echo "('make worktree-clean' inside it, then 'git worktree remove')."
  exit 1
fi

echo "==> Worktree $DIR"
if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
  echo "    branch $BRANCH (existing local branch)"
  git worktree add "$DIR" "$BRANCH"
elif git show-ref --verify --quiet "refs/remotes/origin/$BRANCH"; then
  echo "    branch $BRANCH (tracking origin/$BRANCH)"
  git worktree add --track -b "$BRANCH" "$DIR" "origin/$BRANCH"
else
  echo "    branch $BRANCH (new, from $(git rev-parse --abbrev-ref HEAD) at $(git rev-parse --short HEAD))"
  git worktree add -b "$BRANCH" "$DIR"
fi

# The worktree's own copy: main's would see the main checkout and refuse.
if [ ! -x "$DIR/scripts/worktree/init.sh" ]; then
  echo ""
  echo "FAIL: $BRANCH has no scripts/worktree/init.sh — it predates parallel worktree"
  echo "stacks. The worktree exists at $DIR but has no slot; merge main into"
  echo "$BRANCH, then run 'make worktree-init' inside it."
  exit 1
fi
"$DIR/scripts/worktree/init.sh"

cat <<EOF

Start a session in it:
   cd $DIR && claude
EOF
```

- [ ] **Step 3: Makefile**
  - `.PHONY`: add `worktree-new` before `worktree-init`.
  - `help`, first line under `Parallel worktrees`:
    ```make
    	@echo "  make worktree-new NAME=<name> [BRANCH=<branch>]"
    	@echo "                          - Create .claude/worktrees/<name> on BRANCH (default feat/<name>), then init it"
    ```
  - Target, before `worktree-init:`:
    ```make
    worktree-new:
    	@./scripts/worktree/new.sh "$(NAME)" "$(BRANCH)"
    ```

- [ ] **Step 4: Input guards** — nothing may be created

```bash
make worktree-new; make worktree-new NAME=My_Feed; make worktree-new NAME=ok BRANCH=feat/..bad
git worktree list | wc -l
```

Expected: the usage line; `FAIL: NAME='My_Feed'…`; `FAIL: BRANCH='feat/..bad'…`; `1`.

- [ ] **Step 5: Commit, then the full run** (the new worktree must contain `new.sh`'s sibling `init.sh`, which it does from HEAD)

```bash
chmod +x scripts/worktree/new.sh && bash -n scripts/worktree/new.sh
git add scripts/worktree/new.sh Makefile
git commit -m "feat: make worktree-new"
make worktree-new NAME=wt-smoke BRANCH=chore/wt-smoke | grep -E 'branch|Slot|compose project|cd '
make worktree-new NAME=wt-smoke; echo "exit $?"
```

Expected: `branch chore/wt-smoke (new, from feat/parallel-worktrees at <sha>)`, `==> Slot 1 (newly assigned)`, `slot 1, compose project fullstack-multitenant-next-fastapi-tmp-wt-smoke`, `cd …/.claude/worktrees/wt-smoke && claude`; then `FAIL: … already exists` and `exit 2`. **Keep `wt-smoke`** — Task 8 uses it. Fixes: amend.

- [ ] **Step 6: A branch that predates the feature** — a throwaway branch at `main`, which has no `init.sh`:

```bash
git branch chore/wt-old main
make worktree-new NAME=wt-old BRANCH=chore/wt-old 2>&1 | grep -A1 'predates'
git worktree remove .claude/worktrees/wt-old && git branch -D chore/wt-old
```

Expected: `FAIL: chore/wt-old has no scripts/worktree/init.sh — it predates parallel worktree` and the next line.

---

## Task 7: Documentation

**Files:**
- Modify: `CLAUDE.md` (*Running the Stack*), `README.md` (*Frontend Development (local)*, new *Parallel Work*), `docs/setup/infrastructure.md:37-43`

**Interfaces:** none.

- [ ] **Step 1: `CLAUDE.md`**
  - Line 51: `host ports **3000, 3002 and 8100**, which the` → `host ports **3000, 3002 and 8100** (the main checkout's defaults), which the`
  - Lines 60–61 become:
    ```bash
    make dev-preflight      # verify this checkout's API and portal ports are free
    make dev-tunnel         # ngrok: https://$NGROK_DOMAIN -> localhost:$API_HOST_PORT
    ```
  - Heading `### Service URLs (Docker)` → `### Service URLs (Docker, main checkout defaults)`
  - After that table's closing paragraph (the `ngrok (dev only)` note), before `---`, insert:

    ````markdown
    ### Parallel worktrees

    Each linked git worktree can run its own dev stack — its own database (so its
    own migrations), containers and ports — so two branches can be built at once.

    ```bash
    make worktree-new NAME=feed             # .claude/worktrees/feed on feat/feed, initialised
    make worktree-new NAME=x BRANCH=fix/x   # another branch; an existing one is checked out
    cd .claude/worktrees/feed && claude
    make worktree-clean                     # inside it, before `git worktree remove`
    ```

    | Slot | Internal | Supplier | API | Postgres | Compose project |
    |---|---|---|---|---|---|
    | 0 (main checkout) | base | base | base | base | `COMPOSE_PROJECT_NAME`, else the directory name |
    | N (1–9) | base + 10N | base + 10N | base + 10N | base + 10N | `<main's project>-<worktree dir>` |

    Bases are the main checkout's `*_HOST_PORT`s in its root `.env`, defaulting to
    3000 / 3002 / 8100 / 5434. `make worktree-init` (which `worktree-new` runs)
    assigns the slot once, saves it as `WORKTREE_SLOT`, and writes the slot's ports,
    `ALLOWED_ORIGINS` and `NEXT_PUBLIC_API_URL` into the worktree's env files. Every
    make target and `Dev:` task then follows them.

    - **Use `worktree-new`, not `claude --worktree`.** The latter names the branch
      `worktree-<name>`, bases it on `origin/main`, starts before init has run, and
      on exit deletes the folder without `worktree-clean`, stranding the slot's
      volume and images.
    - **Monitoring and ngrok stay in main.** `make docker-run` refuses in a
      worktree; use `docker-run-core`. `make dev-tunnel` works from any checkout,
      one at a time.
    - **Several projects from this template on one machine?** Give each its own
      block of 100: set the `*_HOST_PORT`s in its root `.env`, and `ALLOWED_ORIGINS`
      and both `NEXT_PUBLIC_API_URL`s to match. Re-run `make worktree-init` in
      existing worktrees to move them along.
    ````

- [ ] **Step 2: `README.md`**
  - Lines 268–269: `# Run the supplier portal (always on 3002)` → `# Run the supplier portal (3002 unless PORT is set)`.
  - Line 277: `> **3000, 3002 and 8100**, which the Compose services publish` → `> **3000, 3002 and 8100** (the defaults), which the Compose services publish`.
  - Insert before `## Testing` (after the `make dev-tunnel` paragraph and its `---`, i.e. as the last subsection of *Running the Application*; move the `---` below it):

    ````markdown
    ### Parallel Work (git worktrees)

    Each linked git worktree can run its own stack — database, containers, ports —
    so two branches can be built side by side, each in its own Claude session.

    **Start**

    ```bash
    make worktree-new NAME=feed                   # .claude/worktrees/feed on feat/feed
    make worktree-new NAME=cv-fix BRANCH=fix/cv   # a different branch name
    cd .claude/worktrees/feed && claude
    ```

    An existing local branch is checked out; one that exists only as
    `origin/<branch>` is tracked (how you pick up a PR branch); otherwise the branch
    is created from the current HEAD. `worktree-new` then runs the worktree's own
    `make worktree-init`: it assigns a slot, copies the env files from the main
    checkout with the slot's values written in, and installs dependencies. For a
    worktree created some other way, run `make worktree-init` inside it.

    Prefer this to `claude --worktree`, which names the branch `worktree-<name>`,
    bases it on `origin/main` (without your unpushed commits), starts the session
    before init has run, and on a clean exit deletes the folder without
    `worktree-clean`.

    **Ports**

    | | Internal portal | Supplier portal | API | PostgreSQL |
    |---|---|---|---|---|
    | Main checkout (slot 0) | 3000 | 3002 | 8100 | 5434 |
    | Worktree slot N (1–9) | 3000+10N | 3002+10N | 8100+10N | 5434+10N |

    Those are the defaults: the bases are the main checkout's `*_HOST_PORT`s in its
    root `.env`. Running several projects built from this template on one machine?
    Give each its own block of 100 (e.g. 3200 / 3202 / 8300) and set
    `ALLOWED_ORIGINS` and both `NEXT_PUBLIC_API_URL`s to match. Re-running
    `make worktree-init` in an existing worktree moves it with its main checkout.

    **Run** — inside the worktree, as in main: `make docker-run-core`; or natively
    `make docker-run-db ENV=development`, `make -C server migrate ENV=development`,
    then `make -C server dev`, `make dev-internal` and `make dev-supplier` (or
    VS Code's `Dev: All` with the worktree open as its own window).

    **Monitoring and the tunnel** stay in the main checkout: Prometheus, Grafana and
    cAdvisor publish fixed ports, and ngrok has one static domain. `make docker-run`
    refuses in a worktree; `make dev-tunnel` works from any checkout, one at a time.

    **Finish**

    ```bash
    make worktree-clean                       # inside the worktree
    cd ../../.. && git worktree remove .claude/worktrees/feed
    git branch -d feat/feed                   # once merged
    ```

    `worktree-clean` stops the worktree's own dev servers (matched by working
    directory, not port alone) and removes its containers, database volume and
    images. It leaves the shared Docker build cache alone.

    **Merging parallel branches**

    - **Two Alembic heads.** Both branches' migrations descend from the same
      revision. After the second merge, `cd server && uv run alembic merge heads -m
      "merge <a> and <b>"` and commit the merge revision.
    - **Contract conflicts.** Never hand-merge `server/openapi.json` or
      `web-app/packages/api-client/src/generated/`: take either side, run
      `make gen-contract`, and commit what it produces.
    ````

- [ ] **Step 3: `docs/setup/infrastructure.md`** — replace lines 37–43 (the "Two more are honoured…" paragraph and its table) with:

  ```markdown
  Four more sit **commented out** in `.env.example`, because the defaults are usually
  right. Set them on a machine where the defaults collide — and when several projects
  built from this template share a machine, give each its own block of 100 (see
  *Parallel worktrees* in `CLAUDE.md`). A git worktree gets its own values from
  `make worktree-init`.

  | Variable | Default | Why you would set it |
  |---|---|---|
  | `INTERNAL_PORTAL_HOST_PORT` | `3000` | Host port for the internal portal, on both paths: Compose publishes it and `make dev-internal` runs `next dev` on it. |
  | `SUPPLIER_PORTAL_HOST_PORT` | `3002` | The same for the supplier portal (`make dev-supplier`). |
  | `API_HOST_PORT` | `8100` | 8000 is what every other FastAPI project on the machine also wants. Host-side only — the container still listens on 8000, so the healthcheck, the Prometheus target and `server:8000` are unaffected. |
  | `POSTGRES_HOST_PORT` | `5434` | 5432 collides with a local Postgres. Host-side only; on the compose network `db` is always 5432. |
  ```

- [ ] **Step 4: Verify** — `make check` passes; `grep -n 'Parallel' CLAUDE.md README.md` shows both new headings; `grep -n 'always on 3002' README.md` returns nothing.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md README.md docs/setup/infrastructure.md
git commit -m "docs: parallel worktrees in CLAUDE.md and README"
```

---

## Task 8: End-to-end — slot 1 beside main

Uses `wt-smoke` from Task 6 (slot 1: 3010 / 3012 / 8110 / 5444). Main's database from Task 4 is running on 5434. Two steps need the user in a browser.

**Files:** none changed. Failures are fixed in the owning task's commit (`git commit --fixup <sha>` then `git rebase --autosquash main` — non-interactive with `GIT_SEQUENCE_EDITOR=:`).

- [ ] **Step 1: Native stack in slot 1**

```bash
cd .claude/worktrees/wt-smoke
make dev-preflight
make docker-run-db ENV=development && make -C server migrate ENV=development
docker ps --format '{{.Names}} {{.Ports}}' | grep -E 'tmp-(wt-smoke-)?db-1'
```

Expected: ports 8110, 3010, 3012 free; migrations applied; two `db-1` containers, `…-tmp-db-1` on 5434 and `…-tmp-wt-smoke-db-1` on 5444.

- [ ] **Step 2: Start the servers** — each in the background, logs to `$TMPDIR`:

```bash
make -C server dev > "$TMPDIR/wt-api.log" 2>&1 &
make dev-internal > "$TMPDIR/wt-int.log" 2>&1 &
make dev-supplier > "$TMPDIR/wt-sup.log" 2>&1 &
sleep 20
curl -s localhost:8110/health; echo
curl -s -o /dev/null -w '%{http_code}\n' localhost:3010 localhost:3012
```

Expected: the health JSON; two 2xx/3xx codes (sign-in redirect is fine).

- [ ] **Step 3: USER — sign in on both portals** — ask the user to sign in at `http://localhost:3010` and `http://localhost:3012`, and to report any error. Meanwhile watch: `grep -i 'azp\|origin' "$TMPDIR/wt-api.log"` — expected: nothing.

- [ ] **Step 4: The user row landed only in slot 1**

```bash
for p in fullstack-multitenant-next-fastapi-tmp fullstack-multitenant-next-fastapi-tmp-wt-smoke; do
  c=$(docker ps -q -f label=com.docker.compose.project=$p -f label=com.docker.compose.service=db)
  echo "$p: $(docker exec "$c" sh -c 'psql -tA -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "select count(*) from \"user\""')"
done
```

Expected: slot 1's count is ≥ 1 and includes the user just signed in; main's count equals its value before Step 3 (record it before Step 3 if unsure).

- [ ] **Step 5: Docker stack in slot 1, without an OpenAI key**

```bash
make dev-kill
bash -c 'source scripts/lib/env.sh && upsert server/.env.development OPENAI_API_KEY ""'
make docker-run-core
sleep 30; docker compose -p fullstack-multitenant-next-fastapi-tmp-wt-smoke -f docker-compose.dev.yml ps --format '{{.Service}} {{.Status}}'
curl -s -o /dev/null -w '%{http_code}\n' localhost:3010 localhost:3012 localhost:8110/health
```

Expected: `server … (healthy)`, both portals `Up`; three 2xx/3xx codes.

- [ ] **Step 6: Tear down**

```bash
make worktree-clean
docker images --format '{{.Repository}}' | grep wt-smoke; echo "images gone: $?"
cd ../../.. && git worktree remove .claude/worktrees/wt-smoke && git branch -D chore/wt-smoke
docker ps --format '{{.Names}}' | grep fullstack-multitenant
make check && make check-contract
```

Expected: `✅ …-wt-smoke removed.`; `images gone: 1`; only main's `…-tmp-db-1` running; both checks pass.

---

## Task 9: Move this checkout to its own block (local, not committed)

**Files (gitignored only):** `.env`, `server/.env.development`, both `.env.local`.

- [ ] **Step 1: Write the block**

```bash
bash <<'EOF'
source scripts/lib/env.sh
upsert .env INTERNAL_PORTAL_HOST_PORT 3200
upsert .env SUPPLIER_PORTAL_HOST_PORT 3202
upsert .env API_HOST_PORT 8300
upsert server/.env.development ALLOWED_ORIGINS "'[\"http://localhost:3200\", \"http://localhost:3202\", \"http://localhost:8300\"]'"
upsert web-app/apps/internal-portal/.env.local NEXT_PUBLIC_API_URL http://localhost:8300
upsert web-app/apps/supplier-portal/.env.local NEXT_PUBLIC_API_URL http://localhost:8300
EOF
grep -h -E '^(INTERNAL|SUPPLIER|API)_[A-Z_]*=|^ALLOWED_ORIGINS=|^NEXT_PUBLIC_API_URL=' .env server/.env.development web-app/apps/*/.env.local
git status --short
```

Expected: the three ports, `ALLOWED_ORIGINS='["http://localhost:3200", "http://localhost:3202", "http://localhost:8300"]'`, two `NEXT_PUBLIC_API_URL=http://localhost:8300`; `git status` clean (all gitignored).

- [ ] **Step 2: Main runs on the block** — `make dev-preflight` → `✅ Ports 8300, 3200, 3202 are free`. Start `make -C server dev`, `make dev-internal`, `make dev-supplier` in the background as in Task 8 Step 2; `curl -s localhost:8300/health`.

- [ ] **Step 3: USER — sign in at `http://localhost:3200` and `http://localhost:3202`.** Then `make dev-kill`. (Docker-path images bake `NEXT_PUBLIC_API_URL`; rebuild with `make docker-build-web` before using `docker-run*` in main.)

- [ ] **Step 4: A new worktree follows the block (Review Focus 5)**

```bash
make worktree-new NAME=wt-block BRANCH=chore/wt-block | grep -E 'Slot|localhost'
```

Expected: `Slot 1`, `3210`, `3212`, `8310`, `5444`.

- [ ] **Step 5: Re-running init carries an existing worktree along** — temporarily move main's API base and re-init:

```bash
bash -c 'source scripts/lib/env.sh && upsert .env API_HOST_PORT 8400'
(cd .claude/worktrees/wt-block && make worktree-init | grep 'API server')
bash -c 'source scripts/lib/env.sh && upsert .env API_HOST_PORT 8300'
(cd .claude/worktrees/wt-block && make worktree-init | grep 'API server' && make worktree-clean | tail -1)
git worktree remove .claude/worktrees/wt-block && git branch -D chore/wt-block
```

Expected: `http://localhost:8410`, then `http://localhost:8310`, then `✅ … removed.`
