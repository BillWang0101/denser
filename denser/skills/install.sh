#!/usr/bin/env bash
# Install the denser-compress Claude Code skill to ~/.claude/skills/.
#
# Usage:  bash denser/skills/install.sh
#
# Exit codes:
#   0 — installed (or already up-to-date)
#   1 — source skill directory missing; likely invoked from wrong cwd
#   2 — target exists and differs; refuse without --force
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$SCRIPT_DIR/denser-compress"
TARGET_ROOT="$HOME/.claude/skills"
TARGET="$TARGET_ROOT/denser-compress"
FORCE=0

for arg in "$@"; do
  case "$arg" in
    --force|-f) FORCE=1 ;;
    --help|-h)
      cat <<EOF
Install the denser-compress Claude Code skill.

Usage: bash install.sh [--force]

  --force   Overwrite an existing installation without prompting.
EOF
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      exit 2
      ;;
  esac
done

if [ ! -d "$SRC" ]; then
  echo "ERROR: source skill directory not found: $SRC" >&2
  echo "Did you run this script from the denser repo root?" >&2
  exit 1
fi

mkdir -p "$TARGET_ROOT"

if [ -d "$TARGET" ] && [ "$FORCE" != "1" ]; then
  if diff -r "$SRC" "$TARGET" >/dev/null 2>&1; then
    echo "denser-compress already installed and up to date at $TARGET"
    exit 0
  fi
  printf "Overwrite existing installation at %s? [y/N] " "$TARGET"
  read -r answer
  case "$answer" in
    y|Y|yes) ;;
    *) echo "Aborted."; exit 2 ;;
  esac
  rm -rf "$TARGET"
fi

cp -R "$SRC" "$TARGET"

cat <<EOF
Installed denser-compress to $TARGET

Contents:
  $(ls "$TARGET" | sed 's/^/    /')

Next steps:
  1. Restart Claude Code (so it picks up the new skill)
  2. In any session, say: "compress this skill at <path>"
  3. To uninstall: rm -rf $TARGET

See denser/skills/README.md for details.
EOF
