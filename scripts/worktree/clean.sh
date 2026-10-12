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

# The project name is host-wide. Compose labels each container with the
# directory of its compose file; one from elsewhere means the name is shared,
# and `down -v` would delete that other project's volumes.
dirs="$(docker ps -a --filter "label=com.docker.compose.project=$PROJECT" \
  --format '{{.Label "com.docker.compose.project.working_dir"}}' | sort -u)"
while IFS= read -r dir; do
  [ -z "$dirs" ] && break
  if [ "$dir" != "$HERE" ] && [ "$dir" != "$(pwd -L)" ]; then
    echo "FAIL: compose project $PROJECT has containers from ${dir:-an unknown directory},"
    echo "not this worktree ($HERE). Nothing was removed."
    exit 1
  fi
done <<< "$dirs"

# A port match is not proof of ownership: only processes whose cwd is inside
# this worktree are stopped. Closing a VS Code terminal does not reliably end
# uvicorn's reloader or next-server, and once the directory is gone nothing
# points at them. 4040 is dev-tunnel's ngrok inspector.
PORTS="${API_HOST_PORT:?} ${WEB_HOST_PORT:?} 4040"
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
# uses. Only the two this project built.
for image in "$PROJECT-server" "$PROJECT-web"; do
  if docker image inspect "$image" > /dev/null 2>&1; then
    docker image rm "$image" > /dev/null && echo "    removed image $image"
  fi
done

echo "✅ $PROJECT removed. 'git worktree remove' can follow."
