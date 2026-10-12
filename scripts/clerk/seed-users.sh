#!/usr/bin/env bash
# Create the dev users in the Clerk development instance.
#
# server/data/clerk-dev-seed.json is COMMITTED ON PURPOSE: fake emails,
# throwaway passwords, and a guard that refuses anything but a development
# instance. Users created through the Backend API are email-verified on
# creation, and skip_password_checks lets them carry those passwords.
#
# Two ordinary users, so isolation can be checked by hand: what one creates,
# the other must never see.
#
# Idempotent. Existing users and their passwords are left alone.
#
# Needs 'make clerk-apply-config' (password sign-in, HIBP off at sign-in) first.
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

echo "==> Users"
users_created=0; users_unchanged=0
while IFS= read -r entry; do
  email="$(jq -r '.email' <<< "$entry")"
  # GET /users returns a bare array; tolerate {data:[...]} too.
  user_id="$(api "/users?email_address=$(jq -rn --arg e "$email" '$e|@uri')" \
    | jq -r 'if type == "array" then . else (.data // []) end | .[0].id // empty')"
  if [ -z "$user_id" ]; then
    api /users -X POST -d "$(jq -c '{
      email_address: [.email],
      password,
      first_name,
      last_name,
      skip_password_checks: true,
      skip_restriction_checks: true
    }' <<< "$entry")" > /dev/null
    echo "    created   $email"
    users_created=$(( users_created + 1 ))
  else
    echo "    unchanged $email"
    users_unchanged=$(( users_unchanged + 1 ))
  fi
done < <(jq -c '.users[]' "$ROSTER")

echo
echo "PASS: users $users_created created, $users_unchanged unchanged."
echo
echo "Sign in on the web app (http://localhost:3000) as either of them;"
echo "the passwords are in $ROSTER."
