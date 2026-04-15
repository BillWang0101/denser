#!/usr/bin/env bash
# denser pre-commit hook.
#
# Installation (inside any git repo that maintains LLM-input files like
# skills, CLAUDE.md, system prompts, memory entries):
#
#     cp path/to/denser/integrations/pre-commit-hook.sh .git/hooks/pre-commit
#     chmod +x .git/hooks/pre-commit
#
# What it does:
#   - Collects files staged for the current commit that look like LLM inputs
#     (skills/*.md, memory/*.md, CLAUDE.md, tools/*.md, *system_prompt*).
#   - Invokes `python -m denser.precommit` to check each against its task
#     type's sweet-spot token ceiling.
#   - Blocks the commit if any file is over the ceiling by >10%.
#
# Bypass: `SKIP_DENSER=1 git commit ...` (for legitimate large configs).
set -euo pipefail

# Only look at added / copied / modified files (not deleted).
staged=$(git diff --cached --name-only --diff-filter=ACM | \
    grep -iE '(skills/.*\.md$|memory/.*\.md$|/CLAUDE\.md$|^CLAUDE\.md$|tools/.*\.(md|json)$|.*system[_-]prompt.*\.md$)' || true)

if [ -z "$staged" ]; then
    exit 0  # Nothing LLM-input-shaped in this commit.
fi

# Try python invocation; fall back silently if denser isn't installed in the
# active environment (we don't want to block users who didn't opt in).
if ! command -v python >/dev/null 2>&1; then
    echo "denser: python not found in PATH; skipping density check."
    exit 0
fi

if ! python -c "import denser" 2>/dev/null; then
    echo "denser: Python package not installed; skipping density check."
    echo "        Install with: pip install denser"
    exit 0
fi

# Pass each staged file to the checker.
# shellcheck disable=SC2086
python -m denser.precommit $staged
