#!/usr/bin/env bash
# Create a Clerk application and write its keys into the four env files.
#
# `clerk env pull` alone is not enough: it writes only the publishable and
# secret keys, and to one file. CLERK_ISSUER — the trust anchor the server
# derives its JWKS URL from — is derived here from the publishable key (base64
# of the frontend-API host). So we pull into a temp file and merge key by key,
# which also leaves every other line of the env files alone.
#
# Not set, because no Clerk API can: ALLOWED_ORIGINS (your deployment's origins)
# and CLERK_WEBHOOK_SIGNING_SECRET (docs/setup/clerk.md §6). Instance settings
# are the next commands' job.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/../.."

# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

APP_NAME="${CLERK_APP_NAME:-Template App Dev}"
PORTALS="web-app/apps/internal-portal web-app/apps/supplier-portal"

if ! command -v jq > /dev/null 2>&1; then
  echo "FAIL: jq is not installed."
  echo "Install it with 'brew install jq'."
  exit 1
fi

# This creates a NEW application; a second one by accident is tedious to undo.
if [ -n "${CLERK_APP_ID:-}" ]; then
  echo "FAIL: CLERK_APP_ID is already set to $CLERK_APP_ID."
  echo "This target creates a NEW application. To reconfigure the existing one,"
  echo "run 'make clerk-apply-config', 'make clerk-apply-roles', 'make clerk-seed-users'."
  echo "To start over, remove CLERK_APP_ID from the root .env first."
  exit 1
fi

# macOS base64 -d emits garbage on unpadded input, so pad first. The payload
# carries a trailing '$'.
derive_issuer() { # derive_issuer <publishable key>
  local payload=$1 host
  payload="${payload#pk_test_}"
  payload="${payload#pk_live_}"
  while [ $(( ${#payload} % 4 )) -ne 0 ]; do payload="${payload}="; done
  host="$(printf '%s' "$payload" | base64 -d 2>/dev/null || true)"
  host="${host%\$}"
  if [ -z "$host" ]; then
    echo "FAIL: could not derive the instance host from the publishable key." >&2
    exit 1
  fi
  printf 'https://%s' "$host"
}

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

echo "==> 1/4 Creating the Clerk application \"$APP_NAME\""
APP_ID="$(clerk apps create "$APP_NAME" --json | jq -r '.application_id // .id // empty')"
if [ -z "$APP_ID" ]; then
  echo "FAIL: 'clerk apps create' did not return an application id."
  exit 1
fi
echo "    $APP_ID"

echo "==> 2/4 Pulling the development instance keys"
clerk env pull --app "$APP_ID" --instance dev --file "$TMP" > /dev/null

# The CLI prefixes the publishable key by the framework it detects in the
# current directory (NEXT_PUBLIC_, VITE_, none, …). Match on the suffix.
PUBLISHABLE_KEY="$(grep -E '^[A-Z_]*CLERK_PUBLISHABLE_KEY=' "$TMP" | head -n 1 | cut -d= -f2- | tr -d '"' || true)"
SECRET_KEY="$(grep -E '^CLERK_SECRET_KEY=' "$TMP" | head -n 1 | cut -d= -f2- | tr -d '"' || true)"

if [ -z "$PUBLISHABLE_KEY" ] || [ -z "$SECRET_KEY" ]; then
  echo "FAIL: 'clerk env pull' did not return both keys. It wrote these names:"
  grep -oE '^[A-Z_]+' "$TMP" || true
  exit 1
fi

ISSUER="$(derive_issuer "$PUBLISHABLE_KEY")"
echo "    issuer $ISSUER"

echo "==> 3/4 Writing env files"
ensure_env_file .env .env.example
upsert .env CLERK_APP_ID "$APP_ID"

ensure_env_file server/.env.development server/.env.example
# server/.env.example quotes its values; match it.
upsert server/.env.development CLERK_SECRET_KEY "$SECRET_KEY" quoted
upsert server/.env.development CLERK_ISSUER "$ISSUER" quoted

for portal in $PORTALS; do
  ensure_env_file "$portal/.env.local" "$portal/.env.example"
  upsert "$portal/.env.local" NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY "$PUBLISHABLE_KEY"
  upsert "$portal/.env.local" CLERK_SECRET_KEY "$SECRET_KEY"
done

echo "==> 4/4 Done"
echo
echo "PASS: \"$APP_NAME\" created; its keys are in .env, server/.env.development"
echo "      and both portals' .env.local."
echo
echo "Next:"
echo "  make clerk-apply-config    instance and organization settings"
echo "  make clerk-apply-roles     the four roles, creator and default role"
echo "  make clerk-seed-users      the dev org and its three users"
echo "  make clerk-bootstrap-oauth optional — Swagger's Authorize button"
echo
echo "Your own app, in a team: make clerk-bootstrap-env CLERK_APP_NAME=\"Template App Dev — <name>\""
echo
echo "NOTE: not set by this script — ALLOWED_ORIGINS in server/.env.development"
echo "      (docs/setup/clerk.md §4) and CLERK_WEBHOOK_SIGNING_SECRET (§6). Restart"
echo "      the dev servers: none of them re-reads its env file."
