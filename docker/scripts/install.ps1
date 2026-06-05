# =============================================================================
# SurfSense — One-line Install Script (Windows / PowerShell)
#
#
# Usage: irm https://raw.githubusercontent.com/MODSetter/SurfSense/main/docker/scripts/install.ps1 | iex
#
# To pass flags, save and run locally:
#   .\install.ps1 -NoWatchtower
#   .\install.ps1 -WatchtowerInterval 3600
#   .\install.ps1 -Variant cuda
#   .\install.ps1 -Variant cuda -GpuCount all
#
# Handles two cases automatically:
#   1. Fresh install        — no prior SurfSense data detected
#   2. Migration from the legacy all-in-one container (surfsense-data volume)
#      Downloads and runs migrate-database.sh --yes, then restores the dump
#      into the new PostgreSQL 17 stack. The user runs one command for both.
# =============================================================================

param(
    [switch]$NoWatchtower,
    [int]$WatchtowerInterval = 86400,
    [ValidateSet("cpu", "cuda", "cuda126")]
    [string]$Variant,
    [string]$GpuCount,
    [switch]$Quiet
)

$ErrorActionPreference = 'Stop'

# ── Configuration ───────────────────────────────────────────────────────────

$RepoRaw            = "https://raw.githubusercontent.com/MODSetter/SurfSense/main"
$InstallDir         = ".\surfsense"
$OldVolume          = "surfsense-data"
$DumpFile           = ".\surfsense_migration_backup.sql"
$KeyFile            = ".\surfsense_migration_secret.key"
$MigrationDoneFile  = "$InstallDir\.migration_done"
$MigrationMode      = $false
$SetupWatchtower    = -not $NoWatchtower
$WatchtowerContainer = "watchtower"

if ($GpuCount -and $GpuCount -notmatch '^([0-9]+|all)$') {
    Write-Host "[SurfSense] ERROR: Invalid -GpuCount '$GpuCount'. Use a number or 'all'." -ForegroundColor Red
    exit 1
}

# ── Output helpers ──────────────────────────────────────────────────────────

function Write-Info    { param([string]$Msg) Write-Host "[SurfSense] " -ForegroundColor Cyan -NoNewline; Write-Host $Msg }
function Write-Ok      { param([string]$Msg) Write-Host "[SurfSense] " -ForegroundColor Green -NoNewline; Write-Host $Msg }
function Write-Warn    { param([string]$Msg) Write-Host "[SurfSense] " -ForegroundColor Yellow -NoNewline; Write-Host $Msg }
function Write-Step    { param([string]$Msg) Write-Host "`n-- $Msg" -ForegroundColor Cyan }
function Write-Err     { param([string]$Msg) Write-Host "[SurfSense] ERROR: $Msg" -ForegroundColor Red; exit 1 }

function Invoke-NativeSafe {
    param([scriptblock]$Command)
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $Command
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
}

# ── Pre-flight checks ──────────────────────────────────────────────────────

Write-Step "Checking prerequisites"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Err "Docker is not installed. Install Docker Desktop: https://docs.docker.com/desktop/install/windows-install/"
}
Write-Ok "Docker found."

Invoke-NativeSafe { docker info *>$null } | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Err "Docker daemon is not running. Please start Docker Desktop and try again."
}
Write-Ok "Docker daemon is running."

Invoke-NativeSafe { docker compose version *>$null } | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Err "Docker Compose is not available. It should be bundled with Docker Desktop."
}
Write-Ok "Docker Compose found."

# ── Wait-for-postgres helper ────────────────────────────────────────────────

function Wait-ForPostgres {
    param([string]$DbUser)
    $maxAttempts = 45
    $attempt = 0

    Write-Info "Waiting for PostgreSQL to accept connections..."
    do {
        $attempt++
        if ($attempt -ge $maxAttempts) {
            Write-Err "PostgreSQL did not become ready after $($maxAttempts * 2) seconds.`nCheck logs: cd $InstallDir; docker compose logs db"
        }
        Start-Sleep -Seconds 2
        Push-Location $InstallDir
        Invoke-NativeSafe { docker compose exec -T db pg_isready -U $DbUser -q *>$null } | Out-Null
        $ready = $LASTEXITCODE -eq 0
        Pop-Location
    } while (-not $ready)

    Write-Ok "PostgreSQL is ready."
}

# ── Stack startup helper ────────────────────────────────────────────────────

function Test-StaleZeroCacheVolume {
    $raw = Invoke-NativeSafe { docker volume ls --format '{{.Name}}' 2>$null }
    if ([string]::IsNullOrWhiteSpace($raw)) { return $false }
    $names = $raw -split "`r?`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    $hasZeroCache = $names -contains 'surfsense-zero-cache'
    $hasZeroInit = $names -contains 'surfsense-zero-init'
    # Pre-fix installs created surfsense-zero-cache but never surfsense-zero-init.
    # Such a volume may hold a half-initialized SQLite replica from an earlier
    # crash-loop. Wiping it forces zero-cache to do a fresh initial sync.
    return ($hasZeroCache -and -not $hasZeroInit)
}

function Invoke-StaleZeroCacheCleanup {
    if (-not (Test-StaleZeroCacheVolume)) { return }

    Write-Warn "Detected pre-existing 'surfsense-zero-cache' volume from an install that"
    Write-Warn "predates the migrations-service fix. It may contain a half-initialized"
    Write-Warn "SQLite replica that would block zero-cache from starting."
    Write-Warn "The volume will be removed in 5 seconds; press Ctrl+C to cancel."
    Start-Sleep -Seconds 5

    Push-Location $InstallDir
    Invoke-NativeSafe { docker compose down --remove-orphans 2>$null } | Out-Null
    Pop-Location
    Invoke-NativeSafe { docker volume rm surfsense-zero-cache 2>$null } | Out-Null
    Write-Ok "Removed surfsense-zero-cache volume; zero-cache will re-sync on next start."
}

function Invoke-StackFailureReport {
    Write-Host ""
    Write-Host "[ERROR] Stack did not reach a healthy state." -ForegroundColor Red
    Write-Host ""
    Write-Info "Recent logs from migrations / zero-cache / backend:"
    Push-Location $InstallDir
    try {
        Invoke-NativeSafe { docker compose logs --tail=60 migrations zero-cache backend 2>&1 } | Write-Host
    } finally {
        Pop-Location
    }

    Write-Host ""
    Write-Host "Recovery hints:" -ForegroundColor Yellow
    Write-Host "  1. Inspect migrations:   cd $InstallDir; docker compose logs migrations"
    Write-Host "  2. Verify publication:   cd $InstallDir; docker compose exec db psql -U surfsense -d surfsense -c 'SELECT pubname FROM pg_publication;'"
    Write-Host "  3. Hard reset zero db:   cd $InstallDir; docker compose down; docker volume rm surfsense-zero-cache; docker compose up -d --wait"
    Write-Host ""
    exit 1
}

function Invoke-ComposeUpWait {
    Push-Location $InstallDir
    try {
        Invoke-NativeSafe { docker compose up -d --wait }
    } finally {
        Pop-Location
    }
    if ($LASTEXITCODE -ne 0) {
        Invoke-StackFailureReport
    }
}

# ── Variant and .env helpers ────────────────────────────────────────────────

function Set-EnvValue {
    param([string]$Path, [string]$Key, [string]$Value)
    $lines = @()
    if (Test-Path $Path) {
        $lines = @(Get-Content $Path)
    }
    $updated = $false
    $newLines = foreach ($line in $lines) {
        if ($line -match "^$([regex]::Escape($Key))=") {
            $updated = $true
            "$Key=$Value"
        } else {
            $line
        }
    }
    if (-not $updated) {
        $newLines += "$Key=$Value"
    }
    Set-Content -Path $Path -Value $newLines
}

function Remove-EnvValue {
    param([string]$Path, [string]$Key)
    if (-not (Test-Path $Path)) { return }
    $newLines = Get-Content $Path | Where-Object { $_ -notmatch "^$([regex]::Escape($Key))=" }
    Set-Content -Path $Path -Value $newLines
}

function Test-NvidiaGpu {
    if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) { return $false }
    Invoke-NativeSafe { nvidia-smi *>$null } | Out-Null
    return ($LASTEXITCODE -eq 0)
}

function Test-NvidiaRuntime {
    $info = Invoke-NativeSafe { docker info 2>$null }
    if ($info -match 'nvidia') { return $true }
    if (Get-Command nvidia-ctk -ErrorAction SilentlyContinue) { return $true }
    if (Get-Command nvidia-container-runtime -ErrorAction SilentlyContinue) { return $true }
    return $false
}

function Get-RecommendedVariant {
    $driver = (Invoke-NativeSafe { nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>$null } | Select-Object -First 1)
    $major = 0
    if ($driver -match '^(\d+)') {
        $major = [int]$Matches[1]
    }
    if ($major -gt 0 -and $major -lt 570) {
        return "cuda126"
    }
    return "cuda"
}

function Resolve-Variant {
    $hasGpu = Test-NvidiaGpu
    $hasRuntime = $false
    $recommended = "cpu"

    if ($hasGpu) {
        $recommended = Get-RecommendedVariant
        $hasRuntime = Test-NvidiaRuntime
    }

    if ($Variant) {
        if ($Variant -eq "cpu") { return "cpu" }
        if (-not $hasGpu) {
            Write-Warn "No NVIDIA GPU detected; falling back to CPU variant."
            return "cpu"
        }
        if (-not $hasRuntime) {
            Write-Warn "NVIDIA GPU detected, but NVIDIA Container Toolkit was not detected; falling back to CPU variant."
            Write-Warn "Install the toolkit before enabling SurfSense GPU acceleration."
            return "cpu"
        }
        return $Variant
    }

    if ($hasGpu -and -not $hasRuntime) {
        Write-Warn "NVIDIA GPU detected, but NVIDIA Container Toolkit was not detected; using CPU variant."
    }

    if ($hasGpu -and $hasRuntime -and -not $Quiet -and [Environment]::UserInteractive) {
        Write-Host ""
        Write-Host "SurfSense detected an NVIDIA GPU." -ForegroundColor Cyan
        $choice = Read-Host "Use GPU acceleration? [Y/n]"
        switch ($choice) {
            "" { return $recommended }
            { $_ -match '^(?i)y(es)?$' } { return $recommended }
            { $_ -match '^(?i)n(o)?$' } { return "cpu" }
            default {
                Write-Warn "Unrecognized choice '$choice'; using CPU variant."
                return "cpu"
            }
        }
    }

    return "cpu"
}

function Set-VariantEnv {
    param([string]$Path, [string]$SelectedVariant, [bool]$AllowExistingUpdate)

    if ((Test-Path $Path) -and -not $AllowExistingUpdate) {
        Write-Warn ".env already exists - keeping your existing configuration."
        Write-Info "To change variants later, edit SURFSENSE_VARIANT and COMPOSE_FILE in $Path, then run docker compose up -d --wait."
        return
    }

    if ($SelectedVariant -eq "cpu") {
        Set-EnvValue -Path $Path -Key "SURFSENSE_VARIANT" -Value ""
        Remove-EnvValue -Path $Path -Key "COMPOSE_FILE"
        Remove-EnvValue -Path $Path -Key "SURFSENSE_GPU_COUNT"
    } else {
        Set-EnvValue -Path $Path -Key "SURFSENSE_VARIANT" -Value $SelectedVariant
        Set-EnvValue -Path $Path -Key "COMPOSE_FILE" -Value "docker-compose.yml;docker-compose.gpu.yml"
        if ($GpuCount) {
            Set-EnvValue -Path $Path -Key "SURFSENSE_GPU_COUNT" -Value $GpuCount
        }
    }

    Remove-EnvValue -Path $Path -Key "COMPOSE_PROFILES"
}

$SelectedVariant = Resolve-Variant

# ── Download files ──────────────────────────────────────────────────────────

Write-Step "Downloading SurfSense files"
Write-Info "Installation directory: $InstallDir"

New-Item -ItemType Directory -Path "$InstallDir\scripts" -Force | Out-Null
New-Item -ItemType Directory -Path "$InstallDir\searxng" -Force | Out-Null

$Files = @(
    @{ Src = "docker/docker-compose.yml";                Dest = "docker-compose.yml" }
    @{ Src = "docker/docker-compose.gpu.yml";            Dest = "docker-compose.gpu.yml" }
    @{ Src = "docker/.env.example";                      Dest = ".env.example" }
    @{ Src = "docker/postgresql.conf";                   Dest = "postgresql.conf" }
    @{ Src = "docker/scripts/migrate-database.ps1";      Dest = "scripts/migrate-database.ps1" }
    @{ Src = "docker/searxng/settings.yml";              Dest = "searxng/settings.yml" }
    @{ Src = "docker/searxng/limiter.toml";              Dest = "searxng/limiter.toml" }
)

foreach ($f in $Files) {
    $destPath = Join-Path $InstallDir $f.Dest
    Write-Info "Downloading $($f.Dest)..."
    try {
        Invoke-WebRequest -Uri "$RepoRaw/$($f.Src)" -OutFile $destPath -UseBasicParsing
    } catch {
        Write-Err "Failed to download $($f.Dest). Check your internet connection and try again."
    }
}

Write-Ok "All files downloaded to $InstallDir/"

# ── Legacy all-in-one detection ─────────────────────────────────────────────

$volumeList = Invoke-NativeSafe { docker volume ls --format '{{.Name}}' 2>$null }
if (($volumeList -split "`n") -contains $OldVolume -and -not (Test-Path $MigrationDoneFile)) {
    $MigrationMode = $true

    if (Test-Path $DumpFile) {
        Write-Step "Migration mode - using existing dump (skipping extraction)"
        Write-Info "Found existing dump: $DumpFile"
        Write-Info "Skipping data extraction - proceeding directly to restore."
        Write-Info "To force a fresh extraction, remove the dump first: Remove-Item $DumpFile"
    } else {
        Write-Step "Migration mode - legacy all-in-one container detected"
        Write-Warn "Volume '$OldVolume' found. Your data will be migrated automatically."
        Write-Warn "PostgreSQL is being upgraded from version 14 to 17."
        Write-Warn "Your original data will NOT be deleted."
        Write-Host ""
        Write-Info "Running data extraction (migrate-database.ps1 -Yes)..."
        Write-Info "Full extraction log: ./surfsense-migration.log"
        Write-Host ""

        $migrateScript = Join-Path $InstallDir "scripts/migrate-database.ps1"
        & $migrateScript -Yes
        if ($LASTEXITCODE -ne 0) {
            Write-Err "Data extraction failed. See ./surfsense-migration.log for details.`nYou can also run migrate-database.ps1 manually with custom flags."
        }

        Write-Host ""
        Write-Ok "Data extraction complete. Proceeding with installation and restore."
    }
}

# ── Set up .env ─────────────────────────────────────────────────────────────

Write-Step "Configuring environment"

$envPath = Join-Path $InstallDir ".env"
$envExamplePath = Join-Path $InstallDir ".env.example"

if (-not (Test-Path $envPath)) {
    Copy-Item $envExamplePath $envPath

    if ($MigrationMode -and (Test-Path $KeyFile)) {
        $SecretKey = (Get-Content $KeyFile -Raw).Trim()
        Write-Ok "Using SECRET_KEY recovered from legacy container."
    } else {
        $bytes = New-Object byte[] 32
        $rng = [System.Security.Cryptography.RNGCryptoServiceProvider]::new()
        $rng.GetBytes($bytes)
        $rng.Dispose()
        $SecretKey = [Convert]::ToBase64String($bytes)
        Write-Ok "Generated new random SECRET_KEY."
    }

    $content = Get-Content $envPath -Raw
    $content = $content -replace 'SECRET_KEY=replace_me_with_a_random_string', "SECRET_KEY=$SecretKey"
    Set-Content -Path $envPath -Value $content -NoNewline

    Set-VariantEnv -Path $envPath -SelectedVariant $SelectedVariant -AllowExistingUpdate $false
    Write-Info "Created $envPath"
} else {
    if ($PSBoundParameters.ContainsKey('Variant')) {
        Set-VariantEnv -Path $envPath -SelectedVariant $SelectedVariant -AllowExistingUpdate $true
        Write-Info "Updated SurfSense image variant in existing $envPath"
    } else {
        Set-VariantEnv -Path $envPath -SelectedVariant $SelectedVariant -AllowExistingUpdate $false
    }
}

# ── Start containers ────────────────────────────────────────────────────────

Invoke-StaleZeroCacheCleanup

if ($MigrationMode) {
    $envContent = Get-Content $envPath
    $DbUser = ($envContent | Select-String '^DB_USER=' | ForEach-Object { ($_ -split '=',2)[1].Trim('"') }) | Select-Object -First 1
    $DbPass = ($envContent | Select-String '^DB_PASSWORD=' | ForEach-Object { ($_ -split '=',2)[1].Trim('"') }) | Select-Object -First 1
    $DbName = ($envContent | Select-String '^DB_NAME=' | ForEach-Object { ($_ -split '=',2)[1].Trim('"') }) | Select-Object -First 1
    if (-not $DbUser) { $DbUser = "surfsense" }
    if (-not $DbPass) { $DbPass = "surfsense" }
    if (-not $DbName) { $DbName = "surfsense" }

    Write-Step "Starting PostgreSQL 17"
    Push-Location $InstallDir
    Invoke-NativeSafe { docker compose up -d db } | Out-Null
    Pop-Location
    Wait-ForPostgres -DbUser $DbUser

    Write-Step "Restoring database"
    if (-not (Test-Path $DumpFile)) {
        Write-Err "Dump file '$DumpFile' not found. The migration script may have failed."
    }
    $DumpFilePath = (Resolve-Path $DumpFile).Path
    Write-Info "Restoring dump into PostgreSQL 17 - this may take a while for large databases..."

    $restoreErrFile = Join-Path $env:TEMP "surfsense_restore_err.log"
    Push-Location $InstallDir
    Invoke-NativeSafe { Get-Content -LiteralPath $DumpFilePath | docker compose exec -T -e "PGPASSWORD=$DbPass" db psql -U $DbUser -d $DbName 2>$restoreErrFile | Out-Null } | Out-Null
    Pop-Location

    $fatalErrors = @()
    if (Test-Path $restoreErrFile) {
        $fatalErrors = Get-Content $restoreErrFile |
            Where-Object { $_ -match '^ERROR:' } |
            Where-Object { $_ -notmatch 'already exists' } |
            Where-Object { $_ -notmatch 'multiple primary keys' }
    }

    if ($fatalErrors.Count -gt 0) {
        Write-Warn "Restore completed with errors (may be harmless pg_dump header noise):"
        $fatalErrors | ForEach-Object { Write-Host $_ }
        Write-Warn "If SurfSense behaves incorrectly, inspect manually."
    } else {
        Write-Ok "Database restored with no fatal errors."
    }

    # Smoke test
    Push-Location $InstallDir
    $tableCount = (Invoke-NativeSafe { docker compose exec -T -e "PGPASSWORD=$DbPass" db psql -U $DbUser -d $DbName -t -c "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>$null }).Trim()
    Pop-Location

    if (-not $tableCount -or $tableCount -eq "0") {
        Write-Warn "Smoke test: no tables found after restore."
        Write-Warn "The restore may have failed silently. Check: cd $InstallDir; docker compose logs db"
    } else {
        Write-Ok "Smoke test passed: $tableCount table(s) restored successfully."
        New-Item -Path $MigrationDoneFile -ItemType File -Force | Out-Null
    }

    Write-Step "Starting all SurfSense services"
    Invoke-ComposeUpWait
    Write-Ok "All services started and healthy."

    Remove-Item $KeyFile -ErrorAction SilentlyContinue

} else {
    Write-Step "Starting SurfSense"
    Invoke-ComposeUpWait
    Write-Ok "All services started and healthy."
}

# ── Watchtower (auto-update) ────────────────────────────────────────────────

if ($SetupWatchtower) {
    $wtHours = [math]::Floor($WatchtowerInterval / 3600)
    Write-Step "Setting up Watchtower (auto-updates every ${wtHours}h)"

    $wtState = Invoke-NativeSafe { docker inspect -f '{{.State.Running}}' $WatchtowerContainer 2>$null }
    if ($LASTEXITCODE -ne 0) { $wtState = "missing" }

    if ($wtState -eq "true") {
        Write-Ok "Watchtower is already running - skipping."
    } else {
        if ($wtState -ne "missing") {
            Write-Info "Removing stopped Watchtower container..."
            Invoke-NativeSafe { docker rm -f $WatchtowerContainer *>$null } | Out-Null
        }
        Invoke-NativeSafe {
            docker run -d `
                --name $WatchtowerContainer `
                --restart unless-stopped `
                -v /var/run/docker.sock:/var/run/docker.sock `
                nickfedor/watchtower `
                --label-enable `
                --interval $WatchtowerInterval *>$null
        } | Out-Null

        if ($LASTEXITCODE -eq 0) {
            Write-Ok "Watchtower started - labeled SurfSense containers will auto-update."
        } else {
            Write-Warn "Could not start Watchtower. You can set it up manually or use: docker compose pull; docker compose up -d --wait"
        }
    }
} else {
    Write-Info "Skipping Watchtower setup (-NoWatchtower flag)."
}

# ── Done ────────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host @"


 .d8888b.                    .d888 .d8888b.                                      
d88P  Y88b                  d88P" d88P  Y88b                                     
Y88b.                       888   Y88b.                                          
 "Y888b.   888  888 888d888 888888 "Y888b.    .d88b.  88888b.  .d8888b   .d88b.  
    "Y88b. 888  888 888P"   888       "Y88b. d8P  Y8b 888 "88b 88K      d8P  Y8b 
      "888 888  888 888     888         "888 88888888 888  888 "Y8888b. 88888888 
Y88b  d88P Y88b 888 888     888   Y88b  d88P Y8b.     888  888      X88 Y8b.     
 "Y8888P"   "Y88888 888     888    "Y8888P"   "Y8888  888  888  88888P'  "Y8888  


"@ -ForegroundColor White

$versionDisplay = (Get-Content $envPath | Select-String '^SURFSENSE_VERSION=' | ForEach-Object { ($_ -split '=',2)[1].Trim('"') }) | Select-Object -First 1
if (-not $versionDisplay) { $versionDisplay = "latest" }
$variantDisplay = (Get-Content $envPath | Select-String '^SURFSENSE_VARIANT=' | ForEach-Object { ($_ -split '=',2)[1].Trim('"') }) | Select-Object -First 1
if (-not $variantDisplay) { $variantDisplay = "cpu" }
$wtHours = [math]::Floor($WatchtowerInterval / 3600)
Write-Host "         OSS Alternative to NotebookLM for Teams  [$versionDisplay]" -ForegroundColor Yellow
Write-Host ("=" * 62) -ForegroundColor Cyan
Write-Host ""

Write-Info "  Frontend:  http://localhost:3929"
Write-Info "  Backend:   http://localhost:8929"
Write-Info "  API Docs:  http://localhost:8929/docs"
Write-Info ""
Write-Info "  Config:    $InstallDir\.env"
Write-Info "  Variant:   $variantDisplay"
Write-Info "  Logs:      cd $InstallDir; docker compose logs -f"
Write-Info "  Stop:      cd $InstallDir; docker compose down"
Write-Info "  Update:    cd $InstallDir; docker compose pull; docker compose up -d --wait"
Write-Info ""

if ($SetupWatchtower) {
    Write-Info "  Watchtower: auto-updates every ${wtHours}h (disable: docker rm -f $WatchtowerContainer)"
} else {
    Write-Warn "  Watchtower skipped. For auto-updates, re-run without -NoWatchtower."
}
Write-Info ""

if ($MigrationMode) {
    Write-Warn "  Migration complete! Open frontend and verify your data."
    Write-Warn "  Once verified, clean up the legacy volume and migration files:"
    Write-Warn "    docker volume rm $OldVolume"
    Write-Warn "    Remove-Item $DumpFile"
    Write-Warn "    Remove-Item $MigrationDoneFile"
} else {
    Write-Warn "  First startup may take a few minutes while images are pulled."
    Write-Warn "  Edit $InstallDir\.env to configure API keys, OAuth, etc."
}
