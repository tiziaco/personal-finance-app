#!/usr/bin/env bash
# Refresh scripts/clerk/config.json from the live development instance.
#
# The file is a projection, not a dump: `clerk config pull` returns ~50 keys,
# and the file names only the ones this app depends on. This rewrites their
# values from the instance and leaves the key set alone, so an unrelated
# dashboard change is not drift.
#
# Two jq details, both load-bearing:
#   1. Leaves are selected by type, not with paths(scalars): paths(f) filters
#      by truthiness and would drop every `false` — most of this file.
#   2. Where the instance reports null, the file keeps its own value.
#
# x_organization_roles is not instance config. It is rebuilt from the Backend
# API (/organization_roles, /role_sets/role_set:default), sorted so diffs show
# changed values, not reordering. With Organizations disabled it becomes null.
#
# Usage:
#   pull-config.sh           rewrite the committed file
#   pull-config.sh --full    print the untrimmed instance config plus the roles
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/../.."

# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

BASELINE=scripts/clerk/config.json

if ! command -v jq > /dev/null 2>&1; then
  echo "FAIL: jq is not installed." >&2
  echo "Install it with 'brew install jq'." >&2
  exit 1
fi

if [ -z "${CLERK_APP_ID:-}" ]; then
  echo "FAIL: CLERK_APP_ID is not set." >&2
  echo "'make clerk-bootstrap-env' writes it to the root .env. See docs/setup/clerk.md." >&2
  exit 1
fi

api() { clerk api "$@" --app "$CLERK_APP_ID" --instance dev < /dev/null; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# Progress on stderr: --full's JSON goes to stdout.
echo "==> Pulling instance config" >&2
clerk config pull --app "$CLERK_APP_ID" --instance dev > "$TMP/live.json"
if ! jq -e . "$TMP/live.json" > /dev/null 2>&1; then
  echo "FAIL: 'clerk config pull' did not return JSON. Response was:" >&2
  cat "$TMP/live.json" >&2
  exit 1
fi

echo "==> Pulling organization roles" >&2
if jq -e '.organization_settings.enabled == true' "$TMP/live.json" > /dev/null; then
  api '/organization_roles?limit=100' > "$TMP/roles.json"
  api '/role_sets/role_set:default' > "$TMP/set.json"
  jq -S -n --slurpfile r "$TMP/roles.json" --slurpfile s "$TMP/set.json" '{
    creator_role: $s[0].creator_role.key,
    default_role: $s[0].default_role.key,
    roles: ([ ($r[0] | .data // .)[]
              | {description, key, name, permissions: ([.permissions[]?.key] | sort)} ]
            | sort_by(.key))
  }' > "$TMP/x.json"
else
  echo null > "$TMP/x.json"
fi

if [ "${1:-}" = "--full" ]; then
  jq -S --slurpfile x "$TMP/x.json" '. + {x_organization_roles: $x[0]}' "$TMP/live.json"
  exit 0
fi

echo "==> Projecting onto $BASELINE" >&2
jq -S -n \
  --slurpfile baseArr "$BASELINE" \
  --slurpfile liveArr "$TMP/live.json" \
  --slurpfile x "$TMP/x.json" '
  $baseArr[0] as $base
  | $liveArr[0] as $live
  | [ $base
      | paths as $p
      | select($p[0] != "x_organization_roles")
      | ($base | getpath($p)) as $v
      | ($v | type) as $t
      | select(($t != "object" and $t != "array") or ($v | length) == 0)
      | $p
    ]
  | reduce .[] as $p ({};
      setpath($p;
        ($live | getpath($p)) as $lv
        | if $lv == null then ($base | getpath($p)) else $lv end))
  | .x_organization_roles = $x[0]
' > "$TMP/next.json"

mv "$TMP/next.json" "$BASELINE"
echo "PASS: $BASELINE now reflects the live development instance." >&2
