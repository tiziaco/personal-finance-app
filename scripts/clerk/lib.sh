#!/usr/bin/env bash
# Shared helpers for scripts/clerk/*. Sourced, never executed.
#
#     source "$(dirname "$0")/lib.sh"

# shellcheck source=../lib/env.sh
source "$(dirname "${BASH_SOURCE[0]}")/../lib/env.sh"

# Make parses the root .env once, so in a chained `make clerk-bootstrap-env
# clerk-apply-config` the later targets miss the id bootstrap-env just wrote.
# Callers cd to the repo root before sourcing this.
CLERK_APP_ID="${CLERK_APP_ID:-$(read_key .env CLERK_APP_ID)}"

# Refuse anything but a development instance, and name the target. Guards the
# TARGET, not the credential: `clerk api` ignores $CLERK_SECRET_KEY when --app is
# passed, and the Makefile exports one anyway. Another project's dev instance
# passes this check, hence the printed name.
require_dev_instance() { # require_dev_instance <app id>
  local app
  app="$(clerk apps list --json | jq -c --arg app "$1" '.[] | select(.application_id == $app)')"
  if ! jq -e '.instances[] | select(.environment_type == "development")
             | .publishable_key | startswith("pk_test_")' <<< "$app" > /dev/null 2>&1; then
    echo "FAIL: $1 has no development instance issuing pk_test_ keys."
    echo "Check CLERK_APP_ID in the root .env against 'clerk apps list'."
    exit 1
  fi
  echo "    target: $(jq -r '.name' <<< "$app") ($1)"
}
