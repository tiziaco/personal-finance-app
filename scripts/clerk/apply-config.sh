#!/usr/bin/env bash
# Apply scripts/clerk/config.json to the development instance.
#
# A PATCH: it asserts only the keys in the file and leaves every other setting
# alone. x_organization_roles is ours, not Clerk's — stripped here, applied by
# apply-roles.sh. --destructive is deliberately not passed: it lets a patch
# delete resources rather than reset them. Extra arguments go to
# `clerk config patch` (e.g. --dry-run). Safe to re-run.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/../.."

# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

BASELINE=scripts/clerk/config.json

if [ -z "${CLERK_APP_ID:-}" ]; then
  echo "FAIL: CLERK_APP_ID is not set."
  echo "'make clerk-bootstrap-env' writes it to the root .env. See docs/setup/clerk.md."
  exit 1
fi

if [ ! -f "$BASELINE" ]; then
  echo "FAIL: $BASELINE not found. Restore it with 'git checkout -- $BASELINE'."
  exit 1
fi

echo "==> Verifying the target is a development instance"
require_dev_instance "$CLERK_APP_ID"

PATCH="$(mktemp)"
trap 'rm -f "$PATCH"' EXIT
jq 'del(.x_organization_roles)' "$BASELINE" > "$PATCH"

echo "==> Applying $BASELINE (minus x_organization_roles)"
clerk config patch --app "$CLERK_APP_ID" --instance dev --file "$PATCH" --yes "$@"

case " $* " in *" --dry-run "*) exit 0 ;; esac

echo "PASS: instance settings match the committed baseline."
echo
echo "Next: 'make clerk-apply-roles'."
