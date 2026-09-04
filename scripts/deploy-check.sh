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

if ! docker network inspect dokploy-network >/dev/null 2>&1; then
  echo "FAIL: the 'dokploy-network' network does not exist."
  echo "The deploy file declares it external because a Dokploy host already"
  echo "provides it — that is why 'external' is correct there. Create it once"
  echo "on this machine:"
  echo "    docker network create dokploy-network"
  exit 1
fi

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
    "$PROJECT-$app" | sed -n 's/^APP_NAME=//p' | head -1)
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

migrate_cid=$("${COMPOSE[@]}" ps -aq migrate) || true
if [ -z "$migrate_cid" ]; then
  echo "FAIL: the migrate container was never created."
  exit 1
fi
for _ in $(seq 1 90); do
  [ "$(docker inspect -f '{{.State.Status}}' "$migrate_cid")" = exited ] && break
  sleep 2
done
# A container still Status: running reports ExitCode 0 (the field's zero
# value, not an error), so without this guard a timeout here would fall
# through as a false "migrate exited 0" and misdirect the diagnosis to server.
if [ "$(docker inspect -f '{{.State.Status}}' "$migrate_cid")" != exited ]; then
  echo "FAIL: migrate did not finish within 180s."
  "${COMPOSE[@]}" logs migrate
  exit 1
fi
migrate_code=$(docker inspect -f '{{.State.ExitCode}}' "$migrate_cid")
if [ "$migrate_code" != 0 ]; then
  echo "FAIL: migrate exited $migrate_code; the server must not be serving."
  "${COMPOSE[@]}" logs migrate
  exit 1
fi
echo "    migrate exited 0"

server_cid=$("${COMPOSE[@]}" ps -aq server) || true
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
