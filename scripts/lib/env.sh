#!/usr/bin/env bash
# Env-file helpers, shared by scripts/clerk/* and scripts/worktree/*. Sourced,
# never executed. Callers write into gitignored env files and must leave
# comments, ordering and unrelated keys alone.
#
#     source "$(dirname "${BASH_SOURCE[0]}")/../lib/env.sh"

# Seed a missing env file from its example, so a fresh clone works instead of
# failing partway through.
ensure_env_file() { # ensure_env_file <path> <example path>
  if [ ! -f "$1" ]; then
    if [ ! -f "$2" ]; then
      echo "FAIL: neither $1 nor $2 exists."
      exit 1
    fi
    cp "$2" "$1"
    echo "    created $1 from $(basename "$2")"
  fi
}

# Replace a key in place, or append it. awk to a temp file rather than
# `sed -i`, whose syntax differs between BSD (macOS) and GNU. The temp file
# starts as a `cp -p` so the mv keeps a secrets file's mode, not the umask's.
upsert() { # upsert <file> <key> <value> [quoted]
  local file=$1 key=$2 value=$3 quoted=${4:-} line
  if [ -n "$quoted" ]; then line="$key=\"$value\""; else line="$key=$value"; fi
  if grep -qE "^[[:space:]]*(export[[:space:]]+)?${key}=" "$file" 2>/dev/null; then
    cp -p "$file" "$file.tmp"
    awk -v key="$key" -v line="$line" '
      $0 ~ "^[[:space:]]*(export[[:space:]]+)?" key "=" { print line; next }
      { print }
    ' "$file" > "$file.tmp" && mv "$file.tmp" "$file"
  else
    # Without a trailing newline the new key would be glued onto the last one.
    [ -s "$file" ] && [ -n "$(tail -c 1 "$file")" ] && printf '\n' >> "$file"
    printf '%s\n' "$line" >> "$file"
  fi
}

# The last value of <key> in <file>, outer quotes stripped; empty if the file
# or key is absent.
read_key() { # read_key <file> <key>
  [ -f "$1" ] || return 0
  # `|| true`: under pipefail an absent key would fail the caller's assignment.
  { grep -E "^[[:space:]]*(export[[:space:]]+)?$2=" "$1" || true; } | tail -n 1 \
    | cut -d= -f2- | sed -e "s/^[\"']//" -e "s/[\"']$//"
}
