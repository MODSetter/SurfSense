# Installs the SurfSense desktop app from its GitHub release:
#
#   irm https://www.surfsense.com/install.ps1 | iex
#
# Downloads SHA256SUMS and SurfSense-Setup.exe from one release tag, checks the
# installer's SHA-256 and that its Authenticode signature is valid and from
# CN=SurfSense, then runs it silently, unless SurfSense is running. Windows x64;
# on Arm the x64 build runs under emulation. Nothing is sent anywhere but the
# downloads themselves.
#
#   $env:SURFSENSE_VERSION = '2.2.4'      install that release instead of the latest
#   $env:SURFSENSE_INSTALL_DRY_RUN = '1'  print the plan; download, ask for and change nothing
#
# A dry run also takes SURFSENSE_FAKE_OS, _ARCH (AMD64, ARM64 or x86),
# _RUNNING (1 or 0) and _LATEST (a tag) in place of this machine and GitHub,
# so install-scripts.test.mjs can walk every branch offline.
#
# Everything runs inside one script block and nothing calls exit: under iex the
# variables would otherwise stay in, and exit would close, the user's window.
# Plain ASCII only, because irm on Windows PowerShell 5.1 decodes GitHub's
# application/octet-stream as Latin-1.

& {
    $ErrorActionPreference = 'Stop'
    # Invoke-WebRequest's progress bar slows a 1 GB download to a crawl on 5.1.
    $ProgressPreference = 'SilentlyContinue'

    $Repo = 'https://github.com/MODSetter/SurfSense'
    $DownloadsPage = 'https://www.surfsense.com/downloads'
    $Installer = 'SurfSense-Setup.exe'
    # electron-builder's NSIS key, named by the UUID v5 of the appId com.surfsense.app.
    $InstallKey = 'Software\9a7516bd-33e2-5724-857c-bd937d1ea1f8'
    $DryRun = $env:SURFSENSE_INSTALL_DRY_RUN -eq '1'

    function Say([string]$Message) { Write-Host "SurfSense: $Message" }
    function Plan([string]$Step) { Write-Host "  $Step" }
    function Finish([string]$Message) {
        if ($DryRun) { Say "A real run would end with: $Message" } else { Say $Message }
    }

    # In a dry run, SURFSENSE_FAKE_<name> stands in for what this machine says.
    function Get-Fake([string]$Name) {
        if (-not $DryRun) { return $null }
        $value = [Environment]::GetEnvironmentVariable("SURFSENSE_FAKE_$Name")
        if ($value) { return $value }
        return $null
    }

    function Get-OS {
        $fake = Get-Fake 'OS'
        if ($fake) { return $fake }
        if ($PSVersionTable.PSEdition -ne 'Core' -or $IsWindows) { return 'Windows' }
        return [string][Environment]::OSVersion.Platform
    }

    # The machine's own architecture: an x64 PowerShell on Arm reports AMD64 for itself.
    function Get-Arch {
        $fake = Get-Fake 'ARCH'
        if ($fake) { return $fake }
        $key = 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Environment'
        $native = (Get-ItemProperty -Path $key -Name PROCESSOR_ARCHITECTURE -ErrorAction SilentlyContinue).PROCESSOR_ARCHITECTURE
        if ($native) { return $native }
        if ($env:PROCESSOR_ARCHITEW6432) { return $env:PROCESSOR_ARCHITEW6432 }
        return $env:PROCESSOR_ARCHITECTURE
    }

    # One tag for every download, so SHA256SUMS and the installer always match even
    # when a release is published between the two requests.
    function Resolve-Tag {
        if ($env:SURFSENSE_VERSION) {
            $tag = 'v' + ($env:SURFSENSE_VERSION -replace '^v', '')
            # \z, not $, which would let a trailing newline through.
            if ($tag -cnotmatch '^v[0-9]+\.[0-9]+\.[0-9]+\z') {
                throw "SURFSENSE_VERSION must be a release number such as 2.2.4, not '$env:SURFSENSE_VERSION'."
            }
            return $tag
        }
        if ($DryRun) {
            Say "Would ask $Repo/releases/latest which release is the latest."
            if ($env:SURFSENSE_FAKE_LATEST) { return $env:SURFSENSE_FAKE_LATEST }
            return '<latest>'
        }
        $request = [System.Net.HttpWebRequest]::Create("$Repo/releases/latest")
        $request.Method = 'HEAD'
        $request.AllowAutoRedirect = $false
        $request.KeepAlive = $false
        try {
            $response = $request.GetResponse()
        } catch [System.Net.WebException] {
            $response = $_.Exception.Response
            if (-not $response) { throw "Could not reach GitHub to find the latest release: $($_.Exception.Message)" }
        }
        try { $location = [string]$response.Headers['Location'] } finally { $response.Close() }
        $tag = ($location -split '/releases/tag/')[-1]
        if ($tag -cnotmatch '^v[0-9]+\.[0-9]+\.[0-9]+\z') {
            throw "Could not tell which release is the latest from GitHub's answer ('$location')."
        }
        return $tag
    }

    function Save-ReleaseFile([string]$Name) {
        $url = "$Repo/releases/download/$tag/$Name"
        if ($DryRun) { Plan "would download $url"; return }
        Say "Downloading $Name."
        try {
            Invoke-WebRequest -Uri $url -OutFile (Join-Path $work $Name) -UseBasicParsing
        } catch {
            $status = $null
            if ($_.Exception.Response) { $status = [int]$_.Exception.Response.StatusCode }
            if ($Name -eq 'SHA256SUMS' -and $status -eq 404) {
                throw "$tag has no SHA256SUMS to check the installer against, so nothing was installed. See $DownloadsPage"
            }
            throw "Could not download $Name from ${tag}: $($_.Exception.Message)"
        }
    }

    function Assert-ListedHash([string]$Name) {
        if ($DryRun) { Plan "would check $Name against SHA256SUMS"; return }
        $expected = $null
        foreach ($line in [IO.File]::ReadAllLines((Join-Path $work 'SHA256SUMS'))) {
            if ($line -match '^([0-9A-Fa-f]{64}) [ *]?(.+?)\s*$' -and $Matches[2] -ceq $Name) {
                $expected = $Matches[1]
                break
            }
        }
        if (-not $expected) { throw "SHA256SUMS on $tag does not list $Name, so nothing was installed." }
        $actual = (Get-FileHash -LiteralPath (Join-Path $work $Name) -Algorithm SHA256).Hash
        if ($actual -ne $expected) { throw "$Name does not match its SHA-256 in SHA256SUMS, so it was not run." }
        Say "$Name matches SHA256SUMS."
    }

    function Assert-Signature([string]$Name) {
        if ($DryRun) { Plan "would check $Name has a Valid Authenticode signature from CN=SurfSense"; return }
        $signature = Get-AuthenticodeSignature -LiteralPath (Join-Path $work $Name)
        $subject = ''
        if ($signature.SignerCertificate) { $subject = $signature.SignerCertificate.Subject }
        if ($signature.Status -ne 'Valid' -or $subject -notmatch '(^|,\s*)CN=SurfSense(,|$)') {
            throw "$Name is not validly signed by SurfSense (status $($signature.Status), signer '$subject'), so it was not run."
        }
        Say "$Name carries a valid signature from SurfSense."
    }

    function Invoke-Installer {
        $exe = Join-Path $work $Installer
        if ($DryRun) { Plan "would run: `"$exe`" /S (and wait)"; return }
        Say 'Installing for this user, which needs no administrator rights.'
        $process = Start-Process -FilePath $exe -ArgumentList '/S' -PassThru
        # Holding the handle keeps ExitCode readable; WaitForExit waits for the
        # installer alone, not for an app it might start.
        $null = $process.Handle
        $process.WaitForExit()
        if ($process.ExitCode -ne 0) { throw "$Installer stopped with exit code $($process.ExitCode)." }
    }

    function Get-InstallLocation {
        if ($DryRun) { Plan "would read InstallLocation from HKCU:\$InstallKey"; return '<install folder>' }
        foreach ($root in 'HKCU:', 'HKLM:') {
            $value = (Get-ItemProperty -Path "$root\$InstallKey" -Name InstallLocation -ErrorAction SilentlyContinue).InstallLocation
            if ($value) { return $value }
        }
        return $null
    }

    # The paths of the running SurfSense.exe processes, those in $Folder when
    # it is given, since the installer closes only what runs from its own folder.
    # CIM, not Get-Process, whose Path a 32-bit PowerShell on x64 Windows leaves
    # empty for the 64-bit app. Another user's process shows no path to either
    # without administrator rights, so only this user's counts.
    function Find-RunningApp([string]$Folder) {
        try {
            $paths = @(Get-CimInstance -ClassName Win32_Process -Filter "Name='SurfSense.exe'" -ErrorAction Stop | ForEach-Object { $_.ExecutablePath })
        } catch {
            $paths = @(Get-Process -Name SurfSense -ErrorAction SilentlyContinue | ForEach-Object { $_.Path })
        }
        $paths = @($paths | Where-Object { $_ })
        if ($Folder) {
            $prefix = $Folder.TrimEnd('\') + '\'
            $paths = @($paths | Where-Object { $_.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase) })
        }
        return $paths
    }

    # Under /S the installer closes a running SurfSense without asking, cutting
    # off a reply the app would otherwise save on quit, so this refuses first,
    # as install.sh does.
    function Assert-NotRunning {
        if ($DryRun) {
            if ((Get-Fake 'RUNNING') -ne '1') { Plan 'would check SurfSense is not running'; return }
            $running = $true
        } else {
            $running = @(Find-RunningApp (Get-InstallLocation)).Count -gt 0
        }
        if ($running) { throw 'SurfSense is running. Quit it, then run this again.' }
    }

    $work = $null
    try {
        if ($DryRun) { Say 'Dry run: nothing is downloaded, changed or installed.' }

        $os = Get-OS
        if ($os -ne 'Windows') {
            throw "This script installs SurfSense on Windows, not $os. On macOS and Linux: curl -fsSL https://www.surfsense.com/install.sh | sh"
        }
        $arch = Get-Arch
        switch ($arch) {
            'AMD64' { }
            'ARM64' { Say 'SurfSense ships for x64 only; on this Arm PC it runs under Windows x64 emulation, which is slower.' }
            default { throw "SurfSense for Windows needs 64-bit Windows; this PC is $arch. See $DownloadsPage" }
        }

        if (-not $DryRun -and $PSVersionTable.PSEdition -ne 'Core') {
            # Windows PowerShell 5.1 may still default to TLS 1.0, which GitHub refuses.
            [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
        }

        $tag = Resolve-Tag
        Say "Installing SurfSense $tag."
        $work = Join-Path ([IO.Path]::GetTempPath()) 'surfsense-install-XXXXXXXX'
        if (-not $DryRun) {
            $work = Join-Path ([IO.Path]::GetTempPath()) ('surfsense-install-' + [Guid]::NewGuid().ToString('N').Substring(0, 8))
            $null = New-Item -ItemType Directory -Path $work
        }

        Assert-NotRunning
        Save-ReleaseFile 'SHA256SUMS'
        Save-ReleaseFile $Installer
        Assert-ListedHash $Installer
        Assert-Signature $Installer
        # Again, since the download takes minutes in which SurfSense may start.
        Assert-NotRunning
        Invoke-Installer

        $location = Get-InstallLocation
        if ($location) {
            Finish "Installed SurfSense $tag in $location. Start it from the Start menu."
        } else {
            Finish "Installed SurfSense $tag. Start it from the Start menu."
        }
    } catch {
        Write-Host "SurfSense: $($_.Exception.Message)" -ForegroundColor Red
    } finally {
        if ($work -and -not $DryRun) { Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue }
    }
}
