# Version line for the hosted / Docker stack: root VERSION, `v0.*` tags,
# docker-build.yml. The desktop app is a separate line on its own number --
# surfsense_local/VERSION and surfsense_local/scripts/bump-version.sh.
#
# Keep in step with bump-version.sh next to it; the two bump the same files.

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path
$VersionFile = Join-Path $RepoRoot "VERSION"

if (-not (Test-Path $VersionFile)) {
    Write-Error "VERSION file not found at $VersionFile"
    exit 1
}

$Version = (Get-Content $VersionFile -Raw).Trim()

if ($Version -notmatch '^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$') {
    Write-Error "'$Version' is not valid semver (expected X.Y.Z)"
    exit 1
}

Write-Host "Bumping the hosted stack to $Version"
Write-Host "---------------------------------"

function Bump-Json {
    param([string]$File)
    if (-not (Test-Path $File)) {
        Write-Host "  SKIP  $File (not found)"
        return
    }
    $content = Get-Content $File -Raw
    $match = [regex]::Match($content, '"version"\s*:\s*"([^"]*)"')
    if (-not $match.Success) {
        Write-Host "  SKIP  $File (no version field found)"
        return
    }
    $old = $match.Groups[1].Value
    if ($old -eq $Version) {
        Write-Host "  OK    $File ($old -- already up to date)"
    } else {
        $content = $content -replace [regex]::Escape("`"version`": `"$old`""), "`"version`": `"$Version`""
        Set-Content $File -Value $content -NoNewline
        Write-Host "  SET   $File ($old -> $Version)"
    }
}

function Bump-Toml {
    param([string]$File)
    if (-not (Test-Path $File)) {
        Write-Host "  SKIP  $File (not found)"
        return
    }
    $content = Get-Content $File -Raw
    $match = [regex]::Match($content, '(?m)^version\s*=\s*"([^"]*)"')
    if (-not $match.Success) {
        Write-Host "  SKIP  $File (no version field found)"
        return
    }
    $old = $match.Groups[1].Value
    if ($old -eq $Version) {
        Write-Host "  OK    $File ($old -- already up to date)"
    } else {
        $content = $content -replace ('(?m)^version\s*=\s*"' + [regex]::Escape($old) + '"'), "version = `"$Version`""
        Set-Content $File -Value $content -NoNewline
        Write-Host "  SET   $File ($old -> $Version)"
    }
}

Bump-Json (Join-Path $RepoRoot "surfsense_web\package.json")
Bump-Toml (Join-Path $RepoRoot "surfsense_backend\pyproject.toml")

Write-Host ""
Write-Host "Syncing lock files..."
if (Get-Command uv -ErrorAction SilentlyContinue) {
    Push-Location (Join-Path $RepoRoot "surfsense_backend")
    uv lock
    Pop-Location
    Write-Host "  OK    surfsense_backend/uv.lock"
} else {
    Write-Host "  SKIP  uv not found -- run 'uv lock' in surfsense_backend/ manually"
}

Write-Host "---------------------------------"
Write-Host "Done. Hosted stack set to $Version"
