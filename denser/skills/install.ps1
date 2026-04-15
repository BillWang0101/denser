# Install the denser-compress Claude Code skill to ~/.claude/skills/.
#
# Usage:  .\install.ps1 [-Force]

[CmdletBinding()]
param(
    [switch]$Force
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Src = Join-Path $ScriptDir "denser-compress"
$TargetRoot = Join-Path $HOME ".claude\skills"
$Target = Join-Path $TargetRoot "denser-compress"

if (-not (Test-Path -LiteralPath $Src -PathType Container)) {
    Write-Host "ERROR: source skill directory not found: $Src" -ForegroundColor Red
    Write-Host "Did you run this script from the denser repo root?" -ForegroundColor Red
    exit 1
}

New-Item -ItemType Directory -Force -Path $TargetRoot | Out-Null

if ((Test-Path -LiteralPath $Target) -and (-not $Force)) {
    # Check if identical first
    $diff = $false
    try {
        $srcFiles = Get-ChildItem -LiteralPath $Src -Recurse -File | Sort-Object FullName
        $tgtFiles = Get-ChildItem -LiteralPath $Target -Recurse -File | Sort-Object FullName
        if ($srcFiles.Count -ne $tgtFiles.Count) {
            $diff = $true
        } else {
            for ($i = 0; $i -lt $srcFiles.Count; $i++) {
                $a = Get-FileHash -LiteralPath $srcFiles[$i].FullName -Algorithm SHA256
                $b = Get-FileHash -LiteralPath $tgtFiles[$i].FullName -Algorithm SHA256
                if ($a.Hash -ne $b.Hash) { $diff = $true; break }
            }
        }
    } catch { $diff = $true }

    if (-not $diff) {
        Write-Host "denser-compress already installed and up to date at $Target"
        exit 0
    }

    $answer = Read-Host "Overwrite existing installation at $Target? [y/N]"
    if ($answer -notmatch '^[yY]') {
        Write-Host "Aborted."
        exit 2
    }
    Remove-Item -LiteralPath $Target -Recurse -Force
}

Copy-Item -LiteralPath $Src -Destination $Target -Recurse -Force

Write-Host ""
Write-Host "Installed denser-compress to $Target" -ForegroundColor Green
Write-Host ""
Write-Host "Contents:"
Get-ChildItem -LiteralPath $Target | ForEach-Object { "    $($_.Name)" }
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Restart Claude Code (so it picks up the new skill)"
Write-Host "  2. In any session, say: ""compress this skill at <path>"""
Write-Host "  3. To uninstall: Remove-Item -Recurse -Force $Target"
Write-Host ""
Write-Host "See denser/skills/README.md for details."
