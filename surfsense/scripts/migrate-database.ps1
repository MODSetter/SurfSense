# =============================================================================
# NeoNote — Database Migration Script (Windows / PowerShell)
#
# Extracts data from the legacy all-in-one surfsense-data volume (PostgreSQL 14)
# and saves it as a SQL dump + SECRET_KEY file ready for install.ps1 to restore.
#
# Usage:
#   .\migrate-database.ps1 [options]
#
# Options:
#   -DbUser USER          Old PostgreSQL username   (default: neonote)
#   -DbPassword PASS      Old PostgreSQL password   (default: neonote)
#   -DbName NAME          Old PostgreSQL database   (default: neonote)
#   -Yes                  Skip all confirmation prompts
#
# Prerequisites:
#   - Docker Desktop installed and running
#   - The legacy surfsense-data volume must exist
#   - ~500 MB free disk space for the dump file
#
# What this script does:
#   1. Stops any container using surfsense-data (to prevent corruption)
#   2. Starts a temporary PG14 container against the old volume
#   3. Dumps the database to .\surfsense_migration_backup.sql
#   4. Recovers the SECRET_KEY to .\surfsense_migration_secret.key
#   5. Exits — leaving installation to install.ps1
#
# What this script does NOT do:
#   - Delete the original surfsense-data volume (do this manually after verifying)
#   - Install the new NeoNote stack (install.ps1 handles that automatically)
#
# Note:
#   install.ps1 downloads and runs this script automatically when it detects the
#   legacy surfsense-data volume. You only need to run this script manually if
#   you have custom database credentials (-DbUser / -DbPassword / -DbName)
#   or if the automatic migration inside install.ps1 fails at the extraction step.
# =============================================================================

param(
    [string]$DbUser     = "neonote",
    [string]$DbPassword = "neonote",
    [string]$DbName     = "neonote",
    [switch]$Yes
)

$ErrorActionPreference = 'Stop'

# ── Constants ────────────────────────────────────────────────────────────────

$OldVolume      = "surfsense-data"
$TempContainer  = "surfsense-pg14-migration"
$DumpFile       = ".\surfsense_migration_backup.sql"
$KeyFile        = ".\surfsense_migration_secret.key"
$PG14Image      = "pgvector/pgvector:pg14"
$LogFile        = ".\neonote-migration.log"

# ── Output helpers ───────────────────────────────────────────────────────────

function Write-Info    { param([string]$Msg) Write-Host "[NeoNote] " -ForegroundColor Cyan -NoNewline; Write-Host $Msg }
function Write-Ok      { param([string]$Msg) Write-Host "[NeoNote] " -ForegroundColor Green -NoNewline; Write-Host $Msg }
function Write-Warn    { param([string]$Msg) Write-Host "[NeoNote] " -ForegroundColor Yellow -NoNewline; Write-Host $Msg }
function Write-Step    { param([string]$Step, [string]$Msg) Write-Host "`n-- Step ${Step}: $Msg" -ForegroundColor Cyan }
function Write-Err     { param([string]$Msg) Write-Host "[NeoNote] ERROR: $Msg" -ForegroundColor Red; exit 1 }

function Log { param([string]$Msg) Add-Content -Path $LogFile -Value $Msg }

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

function Confirm-Action {
    param([string]$Prompt)
    if ($Yes) { return }
    $reply = Read-Host "[NeoNote] $Prompt [y/N]"
    if ($reply -notmatch '^[Yy]$') {
        Write-Warn "Aborted."
        exit 0
    }
}

# ── Cleanup helper ───────────────────────────────────────────────────────────

function Remove-TempContainer {
    $containers = Invoke-NativeSafe { docker ps -a --format '{{.Names}}' 2>$null }
    if ($containers -and ($containers -split "`n") -contains $TempContainer) {
        Write-Info "Cleaning up temporary container '$TempContainer'..."
        Invoke-NativeSafe { docker stop $TempContainer *>$null } | Out-Null
        Invoke-NativeSafe { docker rm $TempContainer *>$null } | Out-Null
    }
}

# Register cleanup on script exit
Register-EngineEvent PowerShell.Exiting -Action {
    $containers = Invoke-NativeSafe { docker ps -a --format '{{.Names}}' 2>$null }
    if ($containers -and ($containers -split "`n") -contains "surfsense-pg14-migration") {
        Invoke-NativeSafe { docker stop "surfsense-pg14-migration" *>$null } | Out-Null
        Invoke-NativeSafe { docker rm "surfsense-pg14-migration" *>$null } | Out-Null
    }
} | Out-Null

# ── Wait-for-postgres helper ────────────────────────────────────────────────

function Wait-ForPostgres {
    param(
        [string]$Container,
        [string]$User,
        [string]$Label = "PostgreSQL"
    )
    $maxAttempts = 45
    $attempt = 0

    Write-Info "Waiting for $Label to accept connections..."
    do {
        $attempt++
        if ($attempt -ge $maxAttempts) {
            Write-Err "$Label did not become ready after $($maxAttempts * 2) seconds. Check: docker logs $Container"
        }
        Start-Sleep -Seconds 2
        Invoke-NativeSafe { docker exec $Container pg_isready -U $User -q 2>$null } | Out-Null
    } while ($LASTEXITCODE -ne 0)

    Write-Ok "$Label is ready."
}

Write-Info "Migrating data from legacy database (PostgreSQL 14 -> 17)"
"Migration started at $(Get-Date)" | Out-File $LogFile

# ── Step 0: Pre-flight checks ───────────────────────────────────────────────

Write-Step "0" "Pre-flight checks"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Err "Docker is not installed. Install Docker Desktop: https://docs.docker.com/desktop/install/windows-install/"
}

Invoke-NativeSafe { docker info *>$null } | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Err "Docker daemon is not running. Please start Docker Desktop and try again."
}

$volumeList = Invoke-NativeSafe { docker volume ls --format '{{.Name}}' 2>$null }
if (-not (($volumeList -split "`n") -contains $OldVolume)) {
    Write-Err "Legacy volume '$OldVolume' not found. Are you sure you ran the old all-in-one NeoNote container?"
}
Write-Ok "Found legacy volume: $OldVolume"

$oldContainer = (Invoke-NativeSafe { docker ps --filter "volume=$OldVolume" --format '{{.Names}}' 2>$null } | Select-Object -First 1)
if ($oldContainer) {
    Write-Warn "Container '$oldContainer' is running and using the '$OldVolume' volume."
    Write-Warn "It must be stopped before migration to prevent data file corruption."
    Confirm-Action "Stop '$oldContainer' now and proceed with data extraction?"
    Invoke-NativeSafe { docker stop $oldContainer *>$null } | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Err "Failed to stop '$oldContainer'. Try: docker stop $oldContainer"
    }
    Write-Ok "Container '$oldContainer' stopped."
}

if (Test-Path $DumpFile) {
    Write-Warn "Dump file '$DumpFile' already exists."
    Write-Warn "If a previous extraction succeeded, just run install.ps1 now."
    Write-Warn "To re-extract, remove the file first: Remove-Item $DumpFile"
    Write-Err "Aborting to avoid overwriting an existing dump."
}

$staleContainers = Invoke-NativeSafe { docker ps -a --format '{{.Names}}' 2>$null }
if ($staleContainers -and ($staleContainers -split "`n") -contains $TempContainer) {
    Write-Warn "Stale migration container '$TempContainer' found - removing it."
    Invoke-NativeSafe { docker stop $TempContainer *>$null } | Out-Null
    Invoke-NativeSafe { docker rm $TempContainer *>$null } | Out-Null
}

$drive = (Get-Item .).PSDrive
$freeMB = [math]::Floor($drive.Free / 1MB)
if ($freeMB -lt 500) {
    Write-Warn "Low disk space: $freeMB MB free. At least 500 MB recommended for the dump."
    Confirm-Action "Continue anyway?"
} else {
    Write-Ok "Disk space: $freeMB MB free."
}

Write-Ok "All pre-flight checks passed."

# ── Confirmation prompt ──────────────────────────────────────────────────────

Write-Host ""
Write-Host "Extraction plan:" -ForegroundColor White
Write-Host "  Source volume   : " -NoNewline; Write-Host "$OldVolume" -ForegroundColor Yellow -NoNewline; Write-Host "  (PG14 data at /data/postgres)"
Write-Host "  Old credentials : user=" -NoNewline; Write-Host "$DbUser" -ForegroundColor Yellow -NoNewline; Write-Host "  db=" -NoNewline; Write-Host "$DbName" -ForegroundColor Yellow
Write-Host "  Dump saved to   : " -NoNewline; Write-Host "$DumpFile" -ForegroundColor Yellow
Write-Host "  SECRET_KEY to   : " -NoNewline; Write-Host "$KeyFile" -ForegroundColor Yellow
Write-Host "  Log file        : " -NoNewline; Write-Host "$LogFile" -ForegroundColor Yellow
Write-Host ""
Confirm-Action "Start data extraction? (Your original data will not be deleted or modified.)"

# ── Step 1: Start temporary PostgreSQL 14 container ──────────────────────────

Write-Step "1" "Starting temporary PostgreSQL 14 container"

Write-Info "Pulling $PG14Image..."
Invoke-NativeSafe { docker pull $PG14Image *>$null } | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Warn "Could not pull $PG14Image - using cached image if available."
}

$dataUid = Invoke-NativeSafe { docker run --rm -v "${OldVolume}:/data" alpine stat -c '%u' /data/postgres 2>$null }
if (-not $dataUid -or $dataUid -eq "0") {
    Write-Warn "Could not detect data directory UID - falling back to default (may chown files)."
    $userFlag = @()
} else {
    Write-Info "Data directory owned by UID $dataUid - starting temp container as that user."
    $userFlag = @("--user", $dataUid)
}

$dockerRunArgs = @(
    "run", "-d",
    "--name", $TempContainer,
    "-v", "${OldVolume}:/data",
    "-e", "PGDATA=/data/postgres",
    "-e", "POSTGRES_USER=$DbUser",
    "-e", "POSTGRES_PASSWORD=$DbPassword",
    "-e", "POSTGRES_DB=$DbName"
) + $userFlag + @($PG14Image)

Invoke-NativeSafe { docker @dockerRunArgs *>$null } | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Err "Failed to start temporary PostgreSQL 14 container."
}

Write-Ok "Temporary container '$TempContainer' started."
Wait-ForPostgres -Container $TempContainer -User $DbUser -Label "PostgreSQL 14"

# ── Step 2: Dump the database ────────────────────────────────────────────────

Write-Step "2" "Dumping PostgreSQL 14 database"

Write-Info "Running pg_dump - this may take a while for large databases..."

$pgDumpErrFile = Join-Path $env:TEMP "surfsense_pgdump_err.log"
Invoke-NativeSafe { docker exec -e "PGPASSWORD=$DbPassword" $TempContainer pg_dump -U $DbUser --no-password $DbName > $DumpFile 2>$pgDumpErrFile } | Out-Null
if ($LASTEXITCODE -ne 0) {
    if (Test-Path $pgDumpErrFile) { Get-Content $pgDumpErrFile | Write-Host -ForegroundColor Red }
    Remove-TempContainer
    Write-Err "pg_dump failed. See above for details."
}

if (-not (Test-Path $DumpFile) -or (Get-Item $DumpFile).Length -eq 0) {
    Remove-TempContainer
    Write-Err "Dump file '$DumpFile' is empty. Something went wrong with pg_dump."
}

$dumpContent = (Get-Content $DumpFile -TotalCount 5) -join "`n"
if ($dumpContent -notmatch "PostgreSQL database dump") {
    Remove-TempContainer
    Write-Err "Dump file does not contain a valid PostgreSQL dump header - the file may be corrupt."
}

$dumpLines = (Get-Content $DumpFile | Measure-Object -Line).Lines
if ($dumpLines -lt 10) {
    Remove-TempContainer
    Write-Err "Dump has only $dumpLines lines - suspiciously small. Aborting."
}

$dumpSize = "{0:N1} MB" -f ((Get-Item $DumpFile).Length / 1MB)
Write-Ok "Dump complete: $dumpSize ($dumpLines lines) -> $DumpFile"

Write-Info "Stopping temporary PostgreSQL 14 container..."
Invoke-NativeSafe { docker stop $TempContainer *>$null } | Out-Null
Invoke-NativeSafe { docker rm $TempContainer *>$null } | Out-Null
Write-Ok "Temporary container removed."

# ── Step 3: Recover SECRET_KEY ───────────────────────────────────────────────

Write-Step "3" "Recovering SECRET_KEY"

$recoveredKey = ""

$keyCheck = Invoke-NativeSafe { docker run --rm -v "${OldVolume}:/data" alpine sh -c 'test -f /data/.secret_key && cat /data/.secret_key' 2>$null }
if ($LASTEXITCODE -eq 0 -and $keyCheck) {
    $recoveredKey = $keyCheck.Trim()
    Write-Ok "Recovered SECRET_KEY from '$OldVolume'."
} else {
    Write-Warn "No SECRET_KEY file found at /data/.secret_key in '$OldVolume'."
    Write-Warn "This means the all-in-one container was launched with SECRET_KEY set as an explicit env var."

    if ($Yes) {
        $bytes = New-Object byte[] 32
        $rng = [System.Security.Cryptography.RNGCryptoServiceProvider]::new()
        $rng.GetBytes($bytes)
        $rng.Dispose()
        $recoveredKey = [Convert]::ToBase64String($bytes)
        Write-Warn "Non-interactive mode: generated a new SECRET_KEY automatically."
        Write-Warn "All active browser sessions will be logged out after migration."
        Write-Warn "To restore your original key, update SECRET_KEY in .\neonote\.env afterwards."
    } else {
        Write-Warn "Enter the SECRET_KEY from your old container's environment"
        $recoveredKey = Read-Host "[NeoNote] (press Enter to generate a new one - existing sessions will be invalidated)"
        if (-not $recoveredKey) {
            $bytes = New-Object byte[] 32
            $rng = [System.Security.Cryptography.RNGCryptoServiceProvider]::new()
            $rng.GetBytes($bytes)
            $rng.Dispose()
            $recoveredKey = [Convert]::ToBase64String($bytes)
            Write-Warn "Generated a new SECRET_KEY. All active browser sessions will be logged out after migration."
        }
    }
}

Set-Content -Path $KeyFile -Value $recoveredKey -NoNewline
Write-Ok "SECRET_KEY saved to $KeyFile"

# ── Done ─────────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host ("=" * 62) -ForegroundColor Green
Write-Host "  Data extraction complete!" -ForegroundColor Green
Write-Host ("=" * 62) -ForegroundColor Green
Write-Host ""

Write-Ok "Dump file : $DumpFile  ($dumpSize)"
Write-Ok "Secret key: $KeyFile"
Write-Host ""
Write-Info "Next step - run install.ps1 from this same directory:"
Write-Host ""
Write-Host "  irm https://raw.githubusercontent.com/MODSetter/NeoNote/main/docker/scripts/install.ps1 | iex" -ForegroundColor Cyan
Write-Host ""
Write-Info "install.ps1 will detect the dump, restore your data into PostgreSQL 17,"
Write-Info "and start the full NeoNote stack automatically."
Write-Host ""
Write-Warn "Keep both files until you have verified the migration:"
Write-Warn "  $DumpFile"
Write-Warn "  $KeyFile"
Write-Warn "Full log saved to: $LogFile"
Write-Host ""

Log "Migration extraction completed successfully at $(Get-Date)"
