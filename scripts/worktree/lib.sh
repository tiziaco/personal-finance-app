#!/usr/bin/env bash
# Helpers shared by scripts/worktree/*. Sourced, never executed.

# shellcheck source=../lib/env.sh
source "$(dirname "${BASH_SOURCE[0]}")/../lib/env.sh"

# The first entry of `git worktree list` is always the main checkout.
main_checkout() {
  git worktree list --porcelain | awk '/^worktree /{ print substr($0, 10); exit }'
}

# Only the main checkout's git dir is the common dir.
is_main_checkout() {
  [ "$(git rev-parse --path-format=absolute --git-dir)" = \
    "$(git rev-parse --path-format=absolute --git-common-dir)" ]
}

# Compose's own rule, so an unset name matches the project Compose runs.
normalize_project_name() { # normalize_project_name <name>
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | sed -e 's/[^a-z0-9_-]//g' -e 's/^[-_]*//'
}

# Main's COMPOSE_PROJECT_NAME, else its directory name. Derived rather than
# fixed, so a fork needs no setting and an existing volume keeps its name.
project_prefix() {
  local main name
  main="$(main_checkout)"
  name="$(read_key "$main/.env" COMPOSE_PROJECT_NAME)"
  normalize_project_name "${name:-$(basename "$main")}"
}
