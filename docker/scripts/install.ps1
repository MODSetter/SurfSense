# SurfSense in Docker: installs it, and updates it when run again (docs/architecture/docker.md).
#
#   irm https://raw.githubusercontent.com/MODSetter/SurfSense/main/docker/scripts/install.ps1 | iex
#
# The install lives in .\surfsense: docker-compose.yml, which each run replaces,
# and .env, which only the first run writes. Needs Docker Desktop.

function Install-SurfSense {
    # A test points this at a local copy of the repository.
    $Source = if ($env:SURFSENSE_INSTALL_SOURCE) { $env:SURFSENSE_INSTALL_SOURCE } else { 'https://raw.githubusercontent.com/MODSetter/SurfSense/main' }
    # Another project's containers in "surfsense" are none of this install's business.
    $env:COMPOSE_IGNORE_ORPHANS = '1'

    # The app's dark palette (frontend-workflow's color/PALETTE.css), since a terminal is
    # usually dark; success is green-500. Every Windows console with VT takes 24-bit colour.
    $colour = $Host.UI.SupportsVirtualTerminal -and -not [Console]::IsOutputRedirected -and -not $env:NO_COLOR
    function Get-Paint([int]$Red, [int]$Green, [int]$Blue) {
        if ($colour) { return "$([char]27)[38;2;$Red;$Green;${Blue}m" } else { return '' }
    }
    $Primary = Get-Paint 217 170 144       # primary #d9aa90
    $Foreground = Get-Paint 232 227 218    # foreground #e8e3da
    $Muted = Get-Paint 142 138 131         # muted-foreground #8e8a83
    $Success = Get-Paint 34 197 94         # green-500 #22c55e
    $Warning = Get-Paint 228 160 60        # warning #e4a03c
    $Destructive = Get-Paint 239 68 68     # destructive #ef4444
    $Bold = if ($colour) { "$([char]27)[1m" } else { '' }
    $Reset = if ($colour) { "$([char]27)[0m" } else { '' }

    function Write-Info([string]$Message) { Write-Host "$Muted[SurfSense]$Reset $Message" }
    function Write-Ok([string]$Message) { Write-Host "$Success[SurfSense] $Message$Reset" }
    function Write-Warn([string]$Message) { Write-Host "$Warning[SurfSense] $Message$Reset" }
    function Write-Step([string]$Message) { Write-Host "`n$Bold$Foreground── $Message$Reset" }
    # The outcome, set apart: heavy rules and an emoji on a terminal, a plain step in a log.
    function Write-Done([string]$Emoji, [string]$Message) {
        if (-not $colour) { Write-Host "`n── $Message"; return }
        $rule = '━' * ($Message.Length + 10)
        Write-Host "`n$Bold$Success$rule`n   $Emoji  $Message`n$rule$Reset"
    }

    function Invoke-Compose {
        Push-Location $InstallDir
        try { & docker compose @args } finally { Pop-Location }
    }

    # As Compose reads it: a quoted value whole, otherwise up to " #".
    function Get-EnvValue([string]$Name) {
        $line = Get-Content (Join-Path $InstallDir '.env') -ErrorAction SilentlyContinue |
            Where-Object { $_ -match "^$Name=" } | Select-Object -Last 1
        if (-not $line) { return '' }
        $value = $line.Substring($Name.Length + 1).TrimEnd("`r")
        if ($value -match '^"([^"]*)"' -or $value -match "^'([^']*)'") { return $Matches[1] }
        return ($value -replace '\s+#.*$', '').Trim()
    }

    function Test-ThisInstall([string]$Dir) {
        $compose = Join-Path $Dir 'docker-compose.yml'
        return (Test-Path $compose) -and [bool](Select-String -Path $compose -Pattern '^  surfsense:' -Quiet)
    }

    function Get-File([string]$From, [string]$To) {
        $target = Join-Path $InstallDir $To
        try {
            (New-Object System.Net.WebClient).DownloadFile("$Source/$From", "$target.download")
        } catch {
            throw "Couldn't download $To. Check your internet connection and try again."
        }
        Move-Item -Force "$target.download" $target
    }

    function Get-ImageId([string]$Image) {
        $id = & docker image inspect --format '{{.Id}}' $Image 2>$null
        if ($LASTEXITCODE -ne 0) { return '' }
        return "$id".Trim()
    }

    function Get-LanAddress {
        try {
            $address = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
                Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' -and $_.InterfaceAlias -notlike 'vEthernet*' } |
                Select-Object -First 1
            if ($address) { return $address.IPAddress }
        } catch {}
        return ''
    }

    # raw.githubusercontent.com refuses Windows PowerShell 5.1's default TLS.
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}

    Write-Host ''
    Write-Host "$Primary" -NoNewline
    Write-Host @'
███████╗██╗   ██╗██████╗ ███████╗███████╗███████╗███╗   ██╗███████╗███████╗
██╔════╝██║   ██║██╔══██╗██╔════╝██╔════╝██╔════╝████╗  ██║██╔════╝██╔════╝
███████╗██║   ██║██████╔╝█████╗  ███████╗█████╗  ██╔██╗ ██║███████╗█████╗
╚════██║██║   ██║██╔══██╗██╔══╝  ╚════██║██╔══╝  ██║╚██╗██║╚════██║██╔══╝
███████║╚██████╔╝██║  ██║██║     ███████║███████╗██║ ╚████║███████║███████╗
╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝     ╚══════╝╚══════╝╚═╝  ╚═══╝╚══════╝╚══════╝
'@
    Write-Host "$Reset" -NoNewline

    Write-Step 'Checking prerequisites'
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw 'Docker is not installed. Install Docker Desktop: https://docs.docker.com/desktop/'
    }
    & docker info *> $null
    if ($LASTEXITCODE -ne 0) { throw 'Docker is not running. Start Docker Desktop and try again.' }
    Write-Ok 'Docker is running.'
    & docker compose version *> $null
    if ($LASTEXITCODE -ne 0) { throw 'Docker Compose is not available. Update Docker Desktop and try again.' }
    Write-Ok 'Docker Compose found.'
    $arch = "$(& docker info --format '{{.Architecture}}' 2>$null)".Trim()
    if ($arch -ne 'x86_64' -and $arch -ne 'amd64') {
        throw "SurfSense runs on x86-64 (amd64) machines only, for now. This one is $(if ($arch) { $arch } else { 'unknown' })."
    }

    # Run again from any folder, it finds the install by its container. The label is
    # read through inspect: Windows PowerShell mangles quotes inside a --format argument.
    $found = ''
    $container = & docker ps -aq --filter 'label=com.docker.compose.project=surfsense' --filter 'label=com.docker.compose.service=surfsense' 2>$null |
        Select-Object -First 1
    if ($container) {
        $labels = (& docker inspect $container 2>$null | Out-String | ConvertFrom-Json)[0].Config.Labels
        $found = $labels.'com.docker.compose.project.working_dir'
    }

    $here = Join-Path (Get-Location).Path 'surfsense'
    if ($found -and (Test-ThisInstall $found)) {
        $InstallDir = $found
    } elseif (Test-Path $here) {
        $InstallDir = $here
        if (-not (Test-ThisInstall $here) -and (Get-ChildItem -Force $here | Select-Object -First 1)) {
            throw '.\surfsense already holds something else. Move it, or run this command from another folder.'
        }
    } else {
        $InstallDir = $here
    }

    $updating = Test-Path (Join-Path $InstallDir '.env')
    if ($updating) {
        Write-Step "Updating SurfSense in $($InstallDir)"
        Write-Info 'Keeping your settings (.env).'
    } else {
        Write-Step 'Downloading SurfSense'
        Write-Info "Installing into $($InstallDir)"
    }

    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
    Get-File 'docker/surfsense/docker-compose.yml' 'docker-compose.yml'
    Get-File 'docker/surfsense/.env.example' '.env.example'
    if (-not $updating) {
        Copy-Item (Join-Path $InstallDir '.env.example') (Join-Path $InstallDir '.env')
        Write-Ok "Created $(Join-Path $InstallDir '.env')"
    }

    $image = "$(Invoke-Compose config --images 2>$null | Select-Object -First 1)".Trim()
    if (-not $image) { throw "docker-compose.yml names no image. Check $(Join-Path $InstallDir '.env')." }
    $before = Get-ImageId $image

    if ($before) { Write-Step 'Pulling SurfSense' } else { Write-Step 'Pulling SurfSense (about 5 GB the first time)' }
    Invoke-Compose pull
    if ($LASTEXITCODE -ne 0) { throw "Couldn't download the SurfSense image. Check your internet connection and try again." }
    $after = Get-ImageId $image

    Write-Step 'Starting SurfSense'
    Write-Info 'Waiting for SurfSense to be ready. A first start takes a minute or two.'
    Invoke-Compose up -d --wait --wait-timeout 600
    if ($LASTEXITCODE -ne 0) {
        Invoke-Compose logs --tail=40 surfsense
        throw "SurfSense didn't start. Logs: cd $($InstallDir); docker compose logs"
    }

    if ($before -and $before -ne $after) {
        # Every version is about 5 GB; the one replaced goes.
        & docker image rm $before *> $null
        if ($LASTEXITCODE -eq 0) { Write-Info 'Removed the previous image.' }
    }

    $version = "$(Invoke-Compose exec -T surfsense cat /app/VERSION 2>$null)".Trim()
    $pinned = Get-EnvValue 'SURFSENSE_VERSION'
    $port = Get-EnvValue 'SURFSENSE_PORT'
    if (-not $port) { $port = '4929' }
    $bind = Get-EnvValue 'SURFSENSE_BIND'
    $domain = Get-EnvValue 'SURFSENSE_DOMAIN'
    $named = if ($version) { "SurfSense $version" } else { 'SurfSense' }

    if (-not $updating) {
        Write-Done ([char]::ConvertFromUtf32(0x1F389)) "$named is running"
    } elseif ($before -eq $after) {
        Write-Done ([char]::ConvertFromUtf32(0x2705)) "$named is already up to date"
    } else {
        Write-Done ([char]::ConvertFromUtf32(0x2728)) "SurfSense updated$(if ($version) { " to $version" })"
    }
    if ($pinned -and $pinned -ne 'latest') {
        Write-Warn "Pinned to $pinned by SURFSENSE_VERSION in $(Join-Path $InstallDir '.env'). Set it to latest to update."
    }

    Write-Host ''
    if ($domain) {
        Write-Host "  Open:      https://$domain"
    } else {
        $address = if ($bind -ne '127.0.0.1') { Get-LanAddress } else { '' }
        if ($address) {
            Write-Host "  Open:      http://${address}:$port    (any device on this network)"
            Write-Host "             http://localhost:$port    (this computer)"
        } else {
            Write-Host "  Open:      http://localhost:$port"
        }
    }
    Write-Host ''
    if (-not $updating) {
        Write-Host '  The first visit asks you to create a password.'
        Write-Host ''
    }
    Write-Host "  Settings:  $(Join-Path $InstallDir '.env')"
    Write-Host "  Logs:      cd $($InstallDir); docker compose logs -f"
    Write-Host "  Stop:      cd $($InstallDir); docker compose down"
    Write-Host '  Update:    run this same command again'
    Write-Host ''
}

try {
    Install-SurfSense
} catch {
    # destructive #ef4444, as Install-SurfSense paints it; its variables stay out of the caller's session.
    $paint = if ($Host.UI.SupportsVirtualTerminal -and -not [Console]::IsOutputRedirected -and -not $env:NO_COLOR) { @("$([char]27)[38;2;239;68;68m", "$([char]27)[0m") } else { @('', '') }
    Write-Host "$($paint[0])[SurfSense] ERROR: $($_.Exception.Message)$($paint[1])"
    # Piped into iex, exit would close the user's window; run as a file, it reports failure.
    if ($PSCommandPath) { exit 1 }
}
