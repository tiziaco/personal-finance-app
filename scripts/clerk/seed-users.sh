#!/usr/bin/env bash
# Create the dev organization and its users in the Clerk development instance.
#
# server/data/clerk-dev-seed.json is COMMITTED ON PURPOSE: fake emails,
# throwaway passwords, and a guard that refuses anything but a development
# instance. Users created through the Backend API are email-verified on
# creation, and skip_password_checks lets them carry those passwords.
#
# One user per internal role. The org is created with the project manager as
# its creator, which exercises the creator role. No supplier: its requests
# need a linked Supplier row (docs/TODO.md, "Clerk — supplier dev seed").
#
# No seeded user may create organizations (create_organization_enabled false);
# tenants are made here or in the dashboard, which the flag does not block. The
# instance default for invitees is a dashboard toggle (docs/setup/clerk.md §1).
#
# Idempotent. Existing users and their passwords are left alone, bar the flag
# above; a membership whose role drifted from the file is updated; memberships
# the file does not name are left alone.
#
# Needs 'make clerk-apply-config' (password sign-in, HIBP off at sign-in) and
# 'make clerk-apply-roles' first.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/../.."

# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

ROSTER=server/data/clerk-dev-seed.json

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

if [ ! -f "$ROSTER" ]; then
  echo "FAIL: $ROSTER not found. Restore it with 'git checkout -- $ROSTER'."
  exit 1
fi

echo "==> Verifying the target is a development instance"
require_dev_instance "$CLERK_APP_ID"

# </dev/null: the loops below read from process substitutions on stdin.
api() { clerk api "$@" --app "$CLERK_APP_ID" --instance dev --yes < /dev/null; }

echo "==> Checking the roster's roles exist"
LIVE_KEYS="$(api '/organization_roles?limit=100' | jq -c '[(.data // .)[].key]')"
MISSING="$(jq -r --argjson live "$LIVE_KEYS" '[.users[].role] - $live | unique | join(", ")' "$ROSTER")"
if [ -n "$MISSING" ]; then
  echo "FAIL: the instance has no role $MISSING. Run 'make clerk-apply-roles' first."
  exit 1
fi

# email -> user id, as JSON (bash 3.2 has no associative arrays).
IDS='{}'
users_created=0; users_updated=0; users_unchanged=0

echo "==> 1/3 Users"
while IFS= read -r entry; do
  email="$(jq -r '.email' <<< "$entry")"
  # GET /users returns a bare array; tolerate {data:[...]} too.
  user="$(api "/users?email_address=$(jq -rn --arg e "$email" '$e|@uri')" \
    | jq -c 'if type == "array" then . else (.data // []) end | .[0] // empty')"
  user_id="$(jq -r '.id // empty' <<< "$user")"
  if [ -z "$user_id" ]; then
    user_id="$(api /users -X POST -d "$(jq -c '{
      email_address: [.email],
      password,
      first_name,
      last_name,
      skip_password_checks: true,
      skip_restriction_checks: true,
      create_organization_enabled: false
    }' <<< "$entry")" | jq -r '.id')"
    echo "    created   $email"
    users_created=$(( users_created + 1 ))
  elif [ "$(jq -r '.create_organization_enabled' <<< "$user")" != false ]; then
    api "/users/$user_id" -X PATCH -d '{"create_organization_enabled":false}' > /dev/null
    echo "    updated   $email (may no longer create organizations)"
    users_updated=$(( users_updated + 1 ))
  else
    echo "    unchanged $email"
    users_unchanged=$(( users_unchanged + 1 ))
  fi
  IDS="$(jq -c --arg e "$email" --arg id "$user_id" '. + {($e): $id}' <<< "$IDS")"
done < <(jq -c '.users[]' "$ROSTER")

echo "==> 2/3 Organization"
ORG_NAME="$(jq -r '.organization.name' "$ROSTER")"
ORG_ID="$(api "/organizations?query=$(jq -rn --arg n "$ORG_NAME" '$n|@uri')&limit=100" \
  | jq -r --arg n "$ORG_NAME" '(.data // .) | map(select(.name == $n)) | .[0].id // empty')"
if [ -z "$ORG_ID" ]; then
  PM_EMAIL="$(jq -r '[.users[] | select(.role == "org:project_manager")][0].email // empty' "$ROSTER")"
  if [ -z "$PM_EMAIL" ]; then
    echo "FAIL: $ROSTER has no org:project_manager to create the organization."
    exit 1
  fi
  ORG_ID="$(api /organizations -X POST -d "$(jq -nc --arg n "$ORG_NAME" \
    --arg by "$(jq -r --arg e "$PM_EMAIL" '.[$e]' <<< "$IDS")" '{name: $n, created_by: $by}')" \
    | jq -r '.id')"
  echo "    created   $ORG_NAME ($ORG_ID), creator $PM_EMAIL"
else
  echo "    unchanged $ORG_NAME ($ORG_ID)"
fi

echo "==> 3/3 Memberships"
MEMBERS="$(api "/organizations/$ORG_ID/memberships?limit=100" | jq -c '.data // .')"
m_created=0; m_updated=0; m_unchanged=0
while IFS= read -r entry; do
  email="$(jq -r '.email' <<< "$entry")"
  role="$(jq -r '.role' <<< "$entry")"
  user_id="$(jq -r --arg e "$email" '.[$e]' <<< "$IDS")"
  current="$(jq -r --arg id "$user_id" \
    'map(select(.public_user_data.user_id == $id)) | .[0].role // empty' <<< "$MEMBERS")"
  if [ -z "$current" ]; then
    api "/organizations/$ORG_ID/memberships" -X POST \
      -d "$(jq -nc --arg u "$user_id" --arg r "$role" '{user_id: $u, role: $r}')" > /dev/null
    echo "    created   $email ($role)"
    m_created=$(( m_created + 1 ))
  elif [ "$current" = "$role" ]; then
    echo "    unchanged $email ($role)"
    m_unchanged=$(( m_unchanged + 1 ))
  else
    api "/organizations/$ORG_ID/memberships/$user_id" -X PATCH \
      -d "$(jq -nc --arg r "$role" '{role: $r}')" > /dev/null
    echo "    updated   $email ($current -> $role)"
    m_updated=$(( m_updated + 1 ))
  fi
done < <(jq -c '.users[]' "$ROSTER")

echo
echo "PASS: users $users_created created, $users_updated updated, $users_unchanged unchanged;"
echo "      memberships $m_created created, $m_updated updated, $m_unchanged unchanged."
echo
echo "Sign in on the internal portal (http://localhost:3000) as any of them;"
echo "the passwords are in $ROSTER."
