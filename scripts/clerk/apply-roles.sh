#!/usr/bin/env bash
# Bring the development instance's organization roles in line with
# x_organization_roles in scripts/clerk/config.json.
#
# Roles are not instance config — `clerk config` has no key for them — so they
# go through the Backend API. Order matters:
#   1. create or update the listed roles, so the pointers below have targets;
#   2. point role_set:default at the creator and default roles;
#   3. point organization_settings at the same two;
#   4. delete unlisted roles last: Clerk refuses to delete the creator role, the
#      domain default role, or a role held by a member or named in an
#      invitation. A refusal is reported, not fatal.
#
# The creator role must hold sys_memberships:manage, sys_memberships:read and
# sys_profile:delete — Clerk derives eligibility from those; there is no flag.
#
# Idempotent: an instance already in line gets no writes.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/../.."

# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

BASELINE=scripts/clerk/config.json
ROLE_SET=role_set:default

if ! command -v jq > /dev/null 2>&1; then
  echo "FAIL: jq is not installed."
  echo "Install it with 'brew install jq'."
  exit 1
fi

if [ -z "${CLERK_APP_ID:-}" ]; then
  echo "FAIL: CLERK_APP_ID is not set."
  echo "'make clerk-bootstrap-env' writes it to the root .env. See docs/setup/clerk.md."
  exit 1
fi

WANT="$(jq -c '.x_organization_roles // empty' "$BASELINE")"
if [ -z "$WANT" ]; then
  echo "FAIL: $BASELINE has no x_organization_roles."
  exit 1
fi

echo "==> Verifying the target is a development instance"
require_dev_instance "$CLERK_APP_ID"

api() { clerk api "$@" --app "$CLERK_APP_ID" --instance dev --yes < /dev/null; }
pull_config() { clerk config pull --app "$CLERK_APP_ID" --instance dev; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

if ! pull_config | jq -e '.organization_settings.enabled == true' > /dev/null 2>&1; then
  echo "FAIL: Organizations are not enabled on this instance."
  echo "Run 'make clerk-apply-config' first."
  exit 1
fi

# The role endpoints take permission ids; the file names permission keys.
PERM_IDS="$(api '/organization_permissions?limit=100' | jq -c '[(.data // .)[] | {(.key): .id}] | add // {}')"
UNKNOWN="$(jq -r --argjson ids "$PERM_IDS" \
  '[.roles[].permissions[] | select($ids[.] == null)] | unique | join(", ")' <<< "$WANT")"
if [ -n "$UNKNOWN" ]; then
  echo "FAIL: the instance has no permission named: $UNKNOWN"
  exit 1
fi

live_roles() { api '/organization_roles?limit=100' | jq -c '.data // .'; }
writes=0

echo "==> 1/4 Roles"
LIVE="$(live_roles)"
while IFS= read -r role; do
  key="$(jq -r '.key' <<< "$role")"
  current="$(jq -c --arg k "$key" 'map(select(.key == $k)) | .[0] // empty' <<< "$LIVE")"
  body="$(jq -c --argjson ids "$PERM_IDS" \
    '{name, description, permissions: [.permissions[] | $ids[.]]}' <<< "$role")"
  if [ -z "$current" ]; then
    api /organization_roles -X POST \
      -d "$(jq -c --arg k "$key" '. + {key: $k, include_in_initial_role_set: true}' <<< "$body")" > /dev/null
    echo "    created   $key"
    writes=$(( writes + 1 ))
  elif [ "$(jq -c '{name, description, permissions: ([.permissions[]?.key] | sort)}' <<< "$current")" \
       = "$(jq -c '{name, description, permissions: (.permissions | sort)}' <<< "$role")" ]; then
    echo "    unchanged $key"
  else
    api "/organization_roles/$(jq -r '.id' <<< "$current")" -X PATCH -d "$body" > /dev/null
    echo "    updated   $key"
    writes=$(( writes + 1 ))
  fi
done < <(jq -c '.roles[]' <<< "$WANT")

echo "==> 2/4 Role set $ROLE_SET"
SET="$(api "/role_sets/$ROLE_SET")"
ABSENT="$(jq -c --argjson set "$SET" '[.roles[].key] - [$set.roles[].key]' <<< "$WANT")"
if [ "$ABSENT" != "[]" ]; then
  api "/role_sets/$ROLE_SET/roles" -X POST -d "$(jq -nc --argjson k "$ABSENT" '{role_keys: $k}')" > /dev/null
  echo "    added     $(jq -r 'join(", ")' <<< "$ABSENT")"
  writes=$(( writes + 1 ))
fi
if [ "$(jq -c '{c: .creator_role.key, d: .default_role.key}' <<< "$SET")" \
   != "$(jq -c '{c: .creator_role, d: .default_role}' <<< "$WANT")" ]; then
  api "/role_sets/$ROLE_SET" -X PATCH \
    -d "$(jq -c '{creator_role_key: .creator_role, default_role_key: .default_role}' <<< "$WANT")" > /dev/null
  echo "    creator $(jq -r '.creator_role' <<< "$WANT"), default $(jq -r '.default_role' <<< "$WANT")"
  writes=$(( writes + 1 ))
else
  echo "    unchanged"
fi

echo "==> 3/4 Organization settings"
WANT_SETTINGS="$(jq -c '{creator_role, domains_default_role: .default_role}' <<< "$WANT")"
if [ "$(pull_config | jq -c '.organization_settings | {creator_role, domains_default_role}')" != "$WANT_SETTINGS" ]; then
  jq -n --argjson s "$WANT_SETTINGS" '{organization_settings: $s}' > "$TMP/patch.json"
  clerk config patch --app "$CLERK_APP_ID" --instance dev --file "$TMP/patch.json" --yes > /dev/null
  echo "    creator_role and domains_default_role set"
  writes=$(( writes + 1 ))
else
  echo "    unchanged"
fi

echo "==> 4/4 Roles not in the baseline"
kept=0
while IFS= read -r extra; do
  key="$(jq -r '.key' <<< "$extra")"
  # Success is judged on the body too: an HTTP error need not fail the CLI.
  if api "/organization_roles/$(jq -r '.id' <<< "$extra")" -X DELETE > "$TMP/delete.out" 2>&1 \
     && jq -e '.deleted == true' "$TMP/delete.out" > /dev/null 2>&1; then
    echo "    deleted   $key"
    writes=$(( writes + 1 ))
  else
    echo "    kept      $key — Clerk refused to delete it:"
    sed 's/^/        /' "$TMP/delete.out"
    kept=$(( kept + 1 ))
  fi
done < <(live_roles | jq -c --argjson want "$WANT" \
  '([$want.roles[].key]) as $k | .[] | select(.key as $x | $k | index($x) | not)')

echo
echo "PASS: roles match $BASELINE ($writes writes)."
if [ "$kept" -gt 0 ]; then
  echo "NOTE: $kept unlisted role(s) kept. A member or an invitation still holds them;"
  echo "      move those to a listed role and re-run."
fi
