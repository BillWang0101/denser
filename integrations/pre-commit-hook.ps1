# denser pre-commit hook for Windows / PowerShell.
#
# Installation (in any git repo):
#   Copy-Item path\to\denser\integrations\pre-commit-hook.ps1 .git\hooks\pre-commit
# then ensure git's `core.hooksPath` is configured OR wrap with a `.sh` trampoline.
#
# Behavior and bypass are identical to pre-commit-hook.sh; see that file for
# details. Use this version when your team's local git is running on Windows.

$ErrorActionPreference = "Stop"

if ($env:SKIP_DENSER) {
    Write-Host "denser: pre-commit check skipped (SKIP_DENSER set)."
    exit 0
}

$staged = git diff --cached --name-only --diff-filter=ACM | Where-Object {
    $_ -match '(skills/.*\.md$|memory/.*\.md$|/CLAUDE\.md$|^CLAUDE\.md$|tools/.*\.(md|json)$|.*system[_-]prompt.*\.md$)'
}

if (-not $staged) {
    exit 0
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "denser: python not found; skipping density check."
    exit 0
}

$importCheck = python -c "import denser" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "denser: Python package not installed; skipping density check."
    Write-Host "        Install with: pip install denser"
    exit 0
}

python -m denser.precommit @staged
exit $LASTEXITCODE
