#!/usr/bin/env bash
# Create a linked worktree under <main>/.claude/worktrees/<name> and give it
# its dev stack: `git worktree add`, then that worktree's own init.sh.
#
#     new.sh <name> [branch]      # branch defaults to feat/<name>
#
# Branch: an existing local branch is checked out; else origin/<branch> is
# tracked (a PR branch); else a new branch starts from the current HEAD.
#
# Why not `claude --worktree`: it names the branch worktree-<name>, bases it on
# origin's default branch, starts before init has run, and on a clean exit
# removes the directory without worktree-clean, stranding the slot's volume and
# images.
#
# NAME is limited to lowercase letters, digits and '-': it becomes part of the
# compose project name, which should match what was typed.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

NAME="${1:-}"
BRANCH="${2:-}"

if [ -z "$NAME" ]; then
  echo "Usage: make worktree-new NAME=<name> [BRANCH=<branch>]   (branch defaults to feat/<name>)"
  exit 1
fi
if ! [[ "$NAME" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
  echo "FAIL: NAME='$NAME'. Use lowercase letters, digits and '-' (it becomes the compose project name)."
  exit 1
fi
BRANCH="${BRANCH:-feat/$NAME}"
if ! git check-ref-format --branch "$BRANCH" > /dev/null 2>&1; then
  echo "FAIL: BRANCH='$BRANCH' is not a valid branch name."
  exit 1
fi

DIR="$(main_checkout)/.claude/worktrees/$NAME"
if [ -e "$DIR" ]; then
  echo "FAIL: $DIR already exists. Pick another NAME, or remove that worktree first"
  echo "('make worktree-clean' inside it, then 'git worktree remove')."
  exit 1
fi

echo "==> Worktree $DIR"
if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
  echo "    branch $BRANCH (existing local branch)"
  git worktree add "$DIR" "$BRANCH"
elif git show-ref --verify --quiet "refs/remotes/origin/$BRANCH"; then
  echo "    branch $BRANCH (tracking origin/$BRANCH)"
  git worktree add --track -b "$BRANCH" "$DIR" "origin/$BRANCH"
else
  echo "    branch $BRANCH (new, from $(git rev-parse --abbrev-ref HEAD) at $(git rev-parse --short HEAD))"
  git worktree add -b "$BRANCH" "$DIR"
fi

# The worktree's own copy: main's would see the main checkout and refuse.
if [ ! -x "$DIR/scripts/worktree/init.sh" ]; then
  echo ""
  echo "FAIL: $BRANCH has no scripts/worktree/init.sh — it predates parallel worktree"
  echo "stacks. The worktree exists at $DIR but has no slot; merge main into"
  echo "$BRANCH, then run 'make worktree-init' inside it."
  exit 1
fi
"$DIR/scripts/worktree/init.sh"

cat <<EOF

Start a session in it:
   cd $DIR && claude
EOF
