[CmdletBinding()]
param(
    [ValidateSet('codex', 'claude', 'both')]
    [string]$Target = 'both',
    [ValidateSet('graphori', 'graphori-dashboard')]
    [string]$Skill = 'graphori',
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$source = Join-Path (Join-Path $repoRoot 'skills') $Skill
$validator = Join-Path $repoRoot 'skills\graphori\scripts\validate_skill.py'
$conflictChecker = Join-Path $repoRoot 'scripts\check_skill_install_conflicts.py'

function Get-HomePath {
    if ($env:HOME) { return $env:HOME }
    return $HOME
}

function Get-Destination([string]$kind) {
    $homePath = Get-HomePath
    if ($kind -eq 'codex') {
        $codexSkillsDir = $env:GRAPHORI_CODEX_SKILLS_DIR
        if (-not $codexSkillsDir) { $codexSkillsDir = Join-Path $homePath '.agents\skills' }
        return Join-Path $codexSkillsDir $Skill
    }
    return Join-Path (Join-Path $homePath '.claude\skills') $Skill
}

function Get-Targets {
    if ($Target -eq 'both') { return @('codex', 'claude') }
    return @($Target)
}

$homePath = Get-HomePath
& python -B $conflictChecker --home $homePath --target $Target --skill $Skill --before-standalone-install
if ($LASTEXITCODE -ne 0) {
    throw 'Graphori standalone installation would duplicate an enabled plugin. Choose one installation route.'
}

function Test-SameTree([string]$left, [string]$right) {
    if (-not (Test-Path -LiteralPath $right -PathType Container)) { return $false }
    $a = Get-ChildItem -LiteralPath $left -Recurse -File | ForEach-Object { $_.FullName.Substring($left.Length).TrimStart('\') }
    $b = Get-ChildItem -LiteralPath $right -Recurse -File | ForEach-Object { $_.FullName.Substring($right.Length).TrimStart('\') }
    if (@($a).Count -ne @($b).Count) { return $false }
    foreach ($relative in $a) {
        $sourceFile = Join-Path $left $relative
        $destFile = Join-Path $right $relative
        if (-not (Test-Path -LiteralPath $destFile -PathType Leaf)) { return $false }
        if ((Get-Sha256 $sourceFile) -ne (Get-Sha256 $destFile)) { return $false }
    }
    return $true
}

function Get-Sha256([string]$path) {
    $algorithm = [Security.Cryptography.SHA256]::Create()
    $stream = [IO.File]::OpenRead($path)
    try {
        return ([BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-', '')
    } finally {
        $stream.Dispose()
        $algorithm.Dispose()
    }
}

foreach ($kind in Get-Targets) {
    $destination = Get-Destination $kind
    if (Test-Path -LiteralPath $destination) {
        if ((Test-SameTree $source $destination)) {
            Write-Host "$kind`: already matches canonical skill; validating."
        } elseif (-not $Force) {
            throw "$kind destination exists and differs: $destination. Use -Force to create a backup and replace it."
        } else {
            $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
            $backup = "$destination.backup-$stamp"
            Move-Item -LiteralPath $destination -Destination $backup
            Write-Host "$kind`: backed up existing skill to $backup"
        }
    }
    if (-not (Test-Path -LiteralPath $destination)) {
        New-Item -ItemType Directory -Path (Split-Path $destination -Parent) -Force | Out-Null
        Copy-Item -LiteralPath $source -Destination $destination -Recurse
        Write-Host "$kind`: installed canonical skill at $destination"
    }
    & python -B $validator $destination
    if ($LASTEXITCODE -ne 0) { throw "$kind validator failed at $destination" }
}
Write-Host 'Graphori skill installation complete.'
