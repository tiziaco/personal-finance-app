# Parallel Worktree Stacks — Design

**Status:** approved design, not yet implemented
**Branch:** `feat/parallel-worktrees`
**Ports:** [`tiziaco/flyorbit`](https://github.com/tiziaco/flyorbit) PR #11 (*parallel worktree stacks, slot + offset*) and PR #12 (*`make worktree-new`*), both merged 24 Sep 2026, adapted for a template with two portals
**Scope:** dev tooling only. No server or web application code changes; `make check-contract` stays clean.

---

## Goal

Let each linked git worktree run its own dev stack — its own database (so its own migrations), containers and ports — so two branches can be built at once, each in its own Claude session.

```bash
make worktree-new NAME=feed        # .claude/worktrees/feed on feat/feed, initialised
cd .claude/worktrees/feed && claude
# … work, then, inside the worktree:
make worktree-clean && cd - && git worktree remove .claude/worktrees/feed
```

---

## Why this differs from the port

flyorbit's scripts land almost verbatim, in the same paths, so future fixes can be diffed across. Five things differ.

1. **Two portals, not one web app.** A slot owns three app ports (internal portal, supplier portal, API), not two, and two `.env.local` files carry `NEXT_PUBLIC_API_URL`. `supplier-portal/package.json` hardcodes `next dev --port 3002`, and the flag beats `PORT`, so it must change.
2. **The template has no fixed compose project name.** flyorbit sets `COMPOSE_PROJECT_NAME=flyorbit` and hardcodes `flyorbit-` as the worktree prefix. Here the main checkout's project is its directory name, and every fork's differs. The prefix is derived (§2).
3. **Base ports are read, not hardcoded.** flyorbit's `init.sh` has `BASE_WEB=3000` etc. as constants. Several projects forked from this template run on one machine, all defaulting to 3000/8100, so each needs its own port block — which only works if the base is configured once, in the main checkout's `.env`, and worktrees follow it (§1).
4. **Postgres stays on 5434.** flyorbit moved its main database 5434 → 5435 to avoid *this* repo. Nothing moves here.
5. **No `scripts/clerk/`.** flyorbit's `scripts/lib/env.sh` also deduplicated the Clerk bootstrap scripts. Here it has only the worktree scripts as callers; it ships in the same place anyway, for parity.

---

## 1. The slot model

| | Internal portal | Supplier portal | API | Postgres | Compose project |
|---|---|---|---|---|---|
| Slot 0 (main checkout) | base | base | base | base | main's (§2) |
| Slot N (1–9, a linked worktree) | base + 10N | base + 10N | base + 10N | base + 10N | `<prefix>-<worktree dir>` |
| Template defaults (slot 0) | 3000 | 3002 | 8100 | 5434 | directory name |

- **Bases** are the main checkout's root `.env` values of `INTERNAL_PORTAL_HOST_PORT`, `SUPPLIER_PORTAL_HOST_PORT`, `API_HOST_PORT`, `POSTGRES_HOST_PORT`, falling back to the template defaults. Always read from **main's** `.env`, never the worktree's: after the first run the worktree's copy holds slot values, not bases.
- **The slot is allocated once** and written into the worktree's `.env` as `WORKTREE_SLOT`. Every later run reuses it. Recomputing it ("first free port") per run would hand out a different answer the day something else held a port, and every URL, browser tab and baked `NEXT_PUBLIC_API_URL` would go stale.
- **Allocation** takes the first N in 1–9 that no other worktree holds (read from each worktree's `.env`) and whose four ports are all free (`lsof -sTCP:LISTEN`). `MAX_SLOT=9`: slot 10 would reach the next project's block.
- **Monitoring never collides with a slot.** Grafana (3001), Prometheus (9090) and cAdvisor (8080) run only in the main checkout (§3).

### One block of 100 ports per project

Slots 0–9 span offsets 0–90, so projects whose bases are 100 apart never overlap. Changing the template's defaults would not help — every fork inherits them. Instead each checkout on a shared machine picks its block in its root `.env`: the four `*_HOST_PORT`s, plus `ALLOWED_ORIGINS` in `server/.env.development` and `NEXT_PUBLIC_API_URL` in both `.env.local` files (which `init.sh` rewrites for worktrees, but which main sets by hand). Re-running `make worktree-init` in an existing worktree after main moves carries the worktree along.

Postgres needs no block: this template's family (5434, 5444, …) and flyorbit's (5435, 5445, …) differ in the last digit.

**This checkout** moves to **3200 / 3202 / 8300** (Postgres stays 5434) as a local, uncommitted step after the implementation (§6). The whole 3200–3292 and 8300–8390 range was free when checked.

---

## 2. Naming

- **Main's project:** `COMPOSE_PROJECT_NAME` from main's root `.env` if set, else main's directory name — Compose's own rule. Nothing is set by default, so an existing checkout's volume (`<dir>_postgres-data`) and data are untouched.
- **Prefix** (`project_prefix` in `scripts/worktree/lib.sh`): that name normalised by Compose's own rule — lowercased, characters outside `[a-z0-9_-]` removed, leading `-`/`_` trimmed — so for an unset name it equals the project Compose actually runs. The worktree directory name is normalised the same way.
- **Worktree project:** `<prefix>-<worktree dir name>`, written into the worktree's `.env`. Written explicitly because Compose would otherwise name it after the bare folder (`feed`), which is neither unique across projects nor recognisable. `init.sh` refuses a name another worktree already uses — two same-named directories in different places would share a database volume.
- **`COMPOSE_PROJECT_NAME` in `.env.example`** is documented but commented out, with the warning that setting it on a checkout that already has data points Compose at a new, empty volume.
- **No `container_name` in `docker-compose.dev.yml`.** A container name is host-global; Compose's `<project>-<service>-<n>` is unique per worktree. Service DNS (`db`, `server:8000`) is per-project network, so it is unaffected. Main's containers are renamed (`db` → `<project>-db-1`); its volume is not, because volume names derive from the project.

---

## 3. Scripts

```
scripts/lib/env.sh           upsert, read_key — env-file helpers
scripts/worktree/lib.sh      main_checkout, project_prefix, is_main_checkout
scripts/worktree/new.sh      make worktree-new NAME=<name> [BRANCH=<branch>]
scripts/worktree/init.sh     make worktree-init
scripts/worktree/clean.sh    make worktree-clean
```

`upsert` is flyorbit's, unchanged: replace a key in place or append it, leaving comments and other keys alone; awk to a temp file rather than `sed -i` (BSD vs GNU); a file without a trailing newline gets one before the append. `read_key` returns a key's value with quotes stripped, empty if absent, and must not fail under `pipefail`.

The main checkout is the first entry of `git worktree list --porcelain`; "am I main" is `git-dir == git-common-dir`.

### `new.sh`

1. `NAME` required, `^[a-z0-9][a-z0-9-]*$` — it becomes part of the compose project name, so a name that needed rewriting would give a project matching nothing typed. `BRANCH` defaults to `feat/<name>` and must pass `git check-ref-format --branch`.
2. Target `<main>/.claude/worktrees/<name>`, whichever checkout it runs from. Refuses if it exists.
3. Branch: an existing local branch is checked out as is; else `origin/<branch>` is tracked; else a new branch from the current HEAD (printed with its commit).
4. Runs **the new worktree's own** `scripts/worktree/init.sh` — main's copy would see the main checkout and refuse. A branch that predates this feature has no `init.sh`: the worktree stays, and the script stops with "merge main into the branch, then `make worktree-init`".

**Why not `claude --worktree`:** it names the branch `worktree-<name>`, bases it on `origin/main` rather than local HEAD, starts the session before init has run (no `.env`, no dependencies), and on a clean exit deletes the folder without `worktree-clean`, stranding the slot's containers, volume and images. The docs say so.

### `init.sh`

1. Refuses in the main checkout, pointing at `make worktree-new`.
2. **Env files**, copied from main only when missing (a re-run never clobbers a hand edit): `.env`, `server/.env.development`, `web-app/apps/internal-portal/.env.local`, `web-app/apps/supplier-portal/.env.local`; `server/.env.test` is optional (only `make test` reads it, against a testcontainer, so nothing in it is slot-dependent). A missing required file in main fails with a pointer to *Environment Setup*.
3. **Slot** (§1): reuse `WORKTREE_SLOT` (must match `^[1-9]$`), else allocate, printing each slot skipped and why. No free slot fails with "remove a finished worktree".
4. **Ports and project** (§1, §2).
5. **Writes** — into the files, not derived at runtime, so each file shows the value in force. Two could not be derived anyway: `server/scripts/set_env.sh` sources `.env.development` with `set -a`, so its `POSTGRES_PORT` beats anything exported; and `ALLOWED_ORIGINS` gates both CORS and Clerk's `azp` check, so a missing origin looks like broken auth.

   | File | Keys |
   |---|---|
   | `.env` | `WORKTREE_SLOT`, `COMPOSE_PROJECT_NAME`, `INTERNAL_PORTAL_HOST_PORT`, `SUPPLIER_PORTAL_HOST_PORT`, `API_HOST_PORT`, `POSTGRES_HOST_PORT` |
   | `server/.env.development` | `POSTGRES_PORT`; `ALLOWED_ORIGINS` = internal, supplier and API origins |
   | both `.env.local` | `NEXT_PUBLIC_API_URL` |

6. **Dependencies:** `uv sync --frozen` in `server/`, `pnpm install --frozen-lockfile` in `web-app/`. Frozen because resolving belongs to whoever changes a dependency; both hard-link from a global cache.
7. Prints the slot, project, URLs, and next steps (Docker or native; monitoring and ngrok stay in main; `worktree-clean` before removal).

Idempotent: a second run leaves every file byte-identical and installs nothing new.

### `clean.sh`

Run through `make worktree-clean`: Compose interpolates the whole file even for `down`, and only the Makefile exports what it requires (`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, from `internal-portal/.env.local`).

1. Refuses in the main checkout (pointing at `docker-stop` / `clean`), and refuses a `COMPOSE_PROJECT_NAME` not of the form `<prefix>-?*` ("was `worktree-init` run here?").
2. **Native servers:** for each listener on the worktree's API, internal and supplier ports and 4040 (ngrok's inspector), stop it only if its cwd is inside this worktree — a port match is not proof of ownership. TERM, poll up to 5 s, then KILL. Closing a VS Code terminal does not reliably end uvicorn's reloader or `next-server`, and once the directory is gone nothing points at them.
3. `$(DOCKER_COMPOSE) -p <project> -f docker-compose.dev.yml down -v --remove-orphans`.
4. Removes the three images the project built — `<project>-server`, `<project>-internal-portal`, `<project>-supplier-portal` — if present. Not `down --rmi all`, which would also remove pulled images (pgvector, ngrok) main is using. Never `docker builder prune`: the build cache is shared by every checkout.

---

## 4. Wiring

**Root `Makefile`**
- `INTERNAL_PORTAL_HOST_PORT ?= 3000`, `SUPPLIER_PORTAL_HOST_PORT ?= 3002`, `WORKTREE_SLOT ?= 0` beside the existing `API_HOST_PORT` / `POSTGRES_HOST_PORT`, with a comment that these are slot 0's.
- `dev-preflight` and every "running at" echo (`docker-run`, `docker-run-core`, `help`) use the variables.
- New: `dev-internal` / `dev-supplier` (`cd web-app && PORT=$(…) pnpm dev:…` — through make because only the Makefile has read the `.env` naming this checkout's ports); `dev-kill` (the three app ports and 4040); `worktree-new`, `worktree-init`, `worktree-clean`.
- `docker-run` refuses when `WORKTREE_SLOT` ≠ 0, pointing at `docker-run-core`: monitoring publishes fixed ports and ngrok claims the one `NGROK_DOMAIN`. `dev-tunnel` works from any checkout, one at a time.

**`server/Makefile`:** `API_HOST_PORT ?= 8100`, `PORT ?= $(API_HOST_PORT)`. It already includes the root `.env`.

**`docker-compose.dev.yml`:** drop `container_name` from `internal-portal`, `supplier-portal`, `migrate`, `server`, `ngrok`, `db`, with a header comment on why; publish `${INTERNAL_PORTAL_HOST_PORT:-3000}:3000` and `${SUPPLIER_PORTAL_HOST_PORT:-3002}:3000`. The portals' `NEXT_PUBLIC_API_URL` build arg is unchanged: the Makefile exports it from `internal-portal/.env.local`, which `init.sh` rewrites.

**`docker-compose.prod.yml`:** header comment only — the dev file now follows the same no-`container_name` rule. Three other comments say the dev file pins `container_name: server` and are corrected: `server/scripts/compose-env.sh`, `server/scripts/docker-image-name.sh`, `server/CLAUDE.md`. The scripts they describe already address the Compose *service*, so no code changes.

**Portal `package.json`s:** `"dev": "next dev --port ${PORT:-3000}"` and `"… ${PORT:-3002}"`. The default stays next to the app that owns it, so plain `pnpm dev:supplier` still works in main; the internal portal is made explicit for symmetry. Relies on pnpm running scripts through `sh`, which the repo already assumes.

**`.vscode/tasks.json`:** `Dev: Internal Portal`, `Dev: Supplier Portal` and `Dev: Kill All` call the make targets; `detail`s say "(3000 in main)" rather than a fixed port. A worktree opened as its own VS Code window then runs `Dev: All` unchanged.

**Root `.env.example`:** the four `*_HOST_PORT`s, commented out at their defaults (the defaults are usually right), with the one-block-per-project rule; commented `COMPOSE_PROJECT_NAME` with the volume warning; commented `WORKTREE_SLOT` ("written by `make worktree-init`; leave unset in main").

**`.gitignore`:** `.claude/worktrees/`.

**Docs**
- `CLAUDE.md`, under *Running the Stack*: a short *Parallel worktrees* subsection — slot table, the three commands, why `worktree-new` over `claude --worktree`, the port-block rule. Port mentions that assumed 3000/3002/8100 say "in main".
- `docs/setup/infrastructure.md`: the host-port table gains the two portal ports and says they are commented out in `.env.example`, not absent from it.
- `README.md`: a *Parallel Work (git worktrees)* section — start, run (native or Docker), monitoring and tunnel stay in main, finish (`worktree-clean`, `git worktree remove`, delete the branch), and merging parallel branches: two Alembic heads need `alembic merge`; conflicts in `server/openapi.json` or the generated client are resolved by `make gen-contract`, never by hand.

### Two independent fixes on the same branch

- **`server/scripts/docker-entrypoint.sh`:** drop `OPENAI_API_KEY` from the default `REQUIRED_ENV_VARS`. `config.py` defaults it to empty and the app starts without it; only an LLM call needs it. Requiring it made the container stricter than the native server, and would make every slot's Docker stack need a key.
- **`server/.env.example`:** `ALLOWED_ORIGINS` lists `http://localhost:3002`. It lists only 3000 and 8100 today, so a fresh clone's supplier portal fails the `azp` check.

---

## 5. Out of scope

- **Monitoring ports** (3001, 9090, 8080) stay fixed and main-only. cAdvisor's 8080 already collides with another project on this machine; that is a separate change.
- **`make clean` in a worktree** still runs `docker builder prune -af`. `worktree-clean` is the documented teardown.
- **A second ngrok domain** per worktree. One tunnel at a time, from any checkout.

---

## 6. Commits and verification

Commits, independent fixes first:

1. `docs: spec parallel worktree stacks`
2. `fix(server): docker entrypoint no longer requires OPENAI_API_KEY`
3. `fix(server): ALLOWED_ORIGINS example lists the supplier portal`
4. `refactor(dev): host ports come from variables` — Makefile vars and targets, compose `ports:`, `server/Makefile`, portal `package.json`s, VS Code tasks. No behaviour change in main.
5. `refactor(dev): drop container_name from the dev compose file`
6. `feat: parallel worktree stacks (slot + offset)` — `scripts/lib/env.sh`, `scripts/worktree/{lib,init,clean}.sh`, `worktree-init` / `worktree-clean`, `docker-run` guard, `.env.example`, `.gitignore`
7. `feat: make worktree-new`
8. `docs: parallel worktrees in CLAUDE.md and README`

Then, locally and uncommitted: move this checkout to 3200 / 3202 / 8300.

Verification:

- **Main after commit 5:** the database runs as `<project>-db-1` on the same `<dir>_postgres-data` volume; Alembic head and row counts unchanged.
- **Scripts:** `bash -n` on each; shellcheck if installed.
- **Guards:** missing or malformed `NAME`, invalid `BRANCH`, existing target directory, `worktree-init` in main, `worktree-clean` in main, `docker-run` in a worktree — each refused with a message, nothing created.
- **`worktree-new NAME=wt-smoke`:** slot 1, ports and project as expected, all keys rewritten. `worktree-init` again: every file byte-identical (checksums). A second worktree gets slot 2.
- **Side by side, native:** slot 1's database beside main's, migrations applied; API and both portals on slot ports; sign-in on **both** portals with no `azp` rejections; the user row only in slot 1's database. *(Browser sign-in: done by the user.)*
- **Side by side, Docker:** `docker-run-core` in slot 1, server healthy with no `OPENAI_API_KEY`, both portals respond.
- **Cleanup:** `worktree-clean` stops only the worktree's processes (a listener on one of its ports started outside it survives), removes its volume and three images; main's container, volume and images remain. Then `git worktree remove` and branch deletion.
- `make check` passes; `make check-contract` clean.
- **After moving main to 3200:** sign-in works on 3200 and 3202 *(user)*; a new worktree gets 3210 / 3212 / 8310.
