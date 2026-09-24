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

# Every check runs before anything is written, so a FAIL leaves no
# half-initialised .env behind (one naming main's project, with no slot).

# ── Env files ────────────────────────────────────────────────────────────────
# server/.env.test is optional: only `make test` reads it, against a testcontainer.
REQUIRED_ENV_FILES=".env server/.env.development web-app/apps/internal-portal/.env.local web-app/apps/supplier-portal/.env.local"
for f in $REQUIRED_ENV_FILES; do
  if [ ! -f "$f" ] && [ ! -f "$MAIN/$f" ]; then
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

# The project namespace is host-wide: `<prefix>-<dir>` can be another
# project's name, whose volume worktree-clean's `down -v` would then delete.
# Checked only when claiming the name; once .env holds it, the stack is ours.
if [ "$(read_key .env COMPOSE_PROJECT_NAME)" != "$PROJECT" ]; then
  if ! docker info > /dev/null 2>&1; then
    echo "WARNING: Docker is unreachable; not checking that compose project $PROJECT is unused."
  else
    label="label=com.docker.compose.project=$PROJECT"
    owned="$(docker ps -a --filter "$label" --format '{{.Names}}'; docker volume ls -q --filter "$label")"
    if [ -n "$owned" ]; then
      echo "FAIL: Docker already has containers or volumes under compose project $PROJECT:"
      echo "$owned" | sed 's/^/    /'
      echo "Rename this worktree's directory ('git worktree move'), or remove the worktree"
      echo "and pick another NAME. Only if they are this worktree's own stale stack from an"
      echo "earlier run, remove them ('docker rm -f', 'docker volume rm') and re-run."
      exit 1
    fi
  fi
fi

# ── Env files ────────────────────────────────────────────────────────────────
# Copied only when missing, so a re-run never clobbers a hand edit.
echo "==> Env files"
for f in $REQUIRED_ENV_FILES server/.env.test; do
  if [ -f "$f" ]; then
    echo "    $f (kept)"
  elif [ -f "$MAIN/$f" ]; then
    cp "$MAIN/$f" "$f"
    echo "    $f (copied from $MAIN)"
  else
    echo "    $f (absent in the main checkout too; skipped)"
  fi
done

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
