[CmdletBinding()]
param(
    [ValidateSet('runtime', 'solo')] [string]$Mode = 'runtime',
    [ValidateSet('codex', 'claude', 'both')] [string]$Target = 'codex',
    [string]$Python = 'python',
    [switch]$DryRun,
    [switch]$Force
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if ($DryRun) {
    if ($Mode -eq 'runtime') { Write-Host "DRY RUN: $Python -m pip install --no-deps $root" }
    else { Write-Host "DRY RUN: powershell -File $PSScriptRoot\install_skill.ps1 -Target $Target$(if ($Force) {' -Force'})" }
    exit 0
}
if ($Mode -eq 'runtime') { & $Python -m pip install --no-deps $root; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }
else { & (Join-Path $PSScriptRoot 'install_skill.ps1') -Target $Target -Force:$Force; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }
