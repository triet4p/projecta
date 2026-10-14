function ConvertTo-ProjectaWebView2Version {
    param([object]$Value)

    if ($Value -isnot [string]) { return $null }
    $text = $Value.Trim()
    if ($text.StartsWith('v', [StringComparison]::OrdinalIgnoreCase)) {
        $text = $text.Substring(1)
    }
    if ($text -notmatch '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$') {
        return $null
    }
    try { return [Version]::Parse($text) } catch { return $null }
}

function Test-ProjectaWebView2Version {
    param(
        [AllowNull()][object]$Value,
        [Parameter(Mandatory)][string]$MinimumVersion
    )

    if ($Value -isnot [string]) { return $false }
    $text = $Value.Trim()
    if ($text -eq '' -or $text -eq '0.0.0.0') { return $false }
    $installed = ConvertTo-ProjectaWebView2Version $Value
    $minimum = ConvertTo-ProjectaWebView2Version $MinimumVersion
    if ($null -eq $installed -or $null -eq $minimum) { return $false }
    return $installed -ge $minimum
}

function Test-ProjectaInstalledWebView2Runtime {
    param(
        [AllowNull()][object]$Versions,
        [Parameter(Mandatory)][string]$MinimumVersion
    )

    if ($null -eq $Versions) { return $false }
    $candidates = @($Versions)
    foreach ($candidate in $candidates) {
        $value = $candidate
        if ($candidate -isnot [string]) {
            if ($null -ne $candidate -and $null -ne $candidate.Version) {
                $value = $candidate.Version
            } else {
                continue
            }
        }
        if (Test-ProjectaWebView2Version -Value $value -MinimumVersion $MinimumVersion) {
            return $true
        }
    }
    return $false
}

function Get-ProjectaInstalledWebView2Runtime {
    # Direct Evergreen Runtime detection only. The Microsoft Edge browser key
    # ({56EB18F8-B008-4CBD-B6D2-8C97FE7E9062}) is never read here: an installed
    # Edge browser is NOT proof that the WebView2 runtime is present.
    # The definitive installer key is Clients (not ClientState); every location
    # below addresses the WebView2 Evergreen GUID only.
    $guid = '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
    $subkey = "SOFTWARE\Microsoft\EdgeUpdate\Clients\$guid"
    $found = @()

    $lm64 = $null
    try {
        $lm64 = [Microsoft.Win32.RegistryKey]::OpenBaseKey(
            [Microsoft.Win32.RegistryHive]::LocalMachine,
            [Microsoft.Win32.RegistryView]::Registry64
        )
        $key = $lm64.OpenSubKey($subkey)
        if ($null -ne $key) {
            try {
                $pv = $key.GetValue('pv')
                if ($null -ne $pv -and [string]$pv -ne '') {
                    $found += [pscustomobject]@{ Version = [string]$pv; Source = 'HKLM-64' }
                }
            } finally {
                $key.Dispose()
            }
        }
    } finally {
        if ($null -ne $lm64) { $lm64.Dispose() }
    }

    $lm32 = $null
    try {
        $lm32 = [Microsoft.Win32.RegistryKey]::OpenBaseKey(
            [Microsoft.Win32.RegistryHive]::LocalMachine,
            [Microsoft.Win32.RegistryView]::Registry32
        )
        $key = $lm32.OpenSubKey($subkey)
        if ($null -ne $key) {
            try {
                $pv = $key.GetValue('pv')
                if ($null -ne $pv -and [string]$pv -ne '') {
                    $found += [pscustomobject]@{ Version = [string]$pv; Source = 'HKLM-32' }
                }
            } finally {
                $key.Dispose()
            }
        }
    } finally {
        if ($null -ne $lm32) { $lm32.Dispose() }
    }

    try {
        $cu = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey(
            "Software\Microsoft\EdgeUpdate\Clients\$guid"
        )
        if ($null -ne $cu) {
            try {
                $pv = $cu.GetValue('pv')
                if ($null -ne $pv -and [string]$pv -ne '') {
                    $found += [pscustomobject]@{ Version = [string]$pv; Source = 'HKCU' }
                }
            } finally {
                $cu.Dispose()
            }
        }
    } catch {
    }

    if ($found.Count -eq 0) { return $null }
    $best = $null
    $bestVersion = $null
    foreach ($candidate in $found) {
        $parsed = ConvertTo-ProjectaWebView2Version $candidate.Version
        if ($null -eq $parsed) { continue }
        if ($null -eq $bestVersion -or $parsed -gt $bestVersion) {
            $bestVersion = $parsed
            $best = $candidate
        }
    }
    if ($null -eq $best) { return $null }
    return [pscustomobject]@{
        Version = $best.Version
        Source = $best.Source
        AllVersions = @($found | ForEach-Object { $_.Version })
    }
}

function Test-ProjectaWebView2InstallerHash {
    param(
        [AllowNull()][object]$Expected,
        [AllowNull()][object]$Actual
    )

    if (
        $Expected -isnot [string] -or
        $Actual -isnot [string] -or
        $Expected -notmatch '^[0-9a-fA-F]{64}$' -or
        $Actual -notmatch '^[0-9a-fA-F]{64}$'
    ) { return $false }
    return [string]::Equals($Expected, $Actual, [StringComparison]::OrdinalIgnoreCase)
}

function Get-ProjectaWebView2FileHash {
    param([Parameter(Mandatory)][string]$Path)

    $algorithm = [System.Security.Cryptography.SHA256]::Create()
    try {
        $stream = [System.IO.File]::OpenRead($Path)
        try {
            $digest = $algorithm.ComputeHash($stream)
            return [BitConverter]::ToString($digest).Replace('-', '').ToLowerInvariant()
        } finally {
            $stream.Dispose()
        }
    } finally {
        $algorithm.Dispose()
    }
}

function Get-ProjectaWebView2AuthenticodeSignature {
    param([Parameter(Mandatory)][string]$Path)

    $modulePath = [System.IO.Path]::GetFullPath(
        $PSHOME + '\Modules\Microsoft.PowerShell.Security\Microsoft.PowerShell.Security.psd1'
    )
    $module = Get-Module -Name Microsoft.PowerShell.Security
    if ($null -eq $module) {
        Import-Module -Name $modulePath -ErrorAction Stop
    } elseif ([string]::Compare(
        $module.Path,
        $modulePath,
        [StringComparison]::OrdinalIgnoreCase
    ) -ne 0) {
        throw 'The loaded PowerShell Authenticode module is not the Windows inbox module.'
    }
    return Get-AuthenticodeSignature -LiteralPath $Path -ErrorAction Stop
}

function Test-ProjectaWebView2BootstrapperMetadata {
    param(
        [Parameter(Mandatory)][object]$Metadata,
        [Parameter(Mandatory)][object]$Policy
    )

    if ($Metadata.SignatureStatus -ne 'Valid') {
        return [pscustomobject]@{ Accepted = $false; Reason = 'The Microsoft Authenticode signature is invalid.'; Code = 'InvalidSignature' }
    }
    if (
        $Policy.integrityContract -ne 'sha256-of-authenticode-verified-download-rechecked-before-launch' -or
        -not (Test-ProjectaWebView2InstallerHash -Expected $Metadata.Sha256 -Actual $Metadata.Sha256)
    ) {
        return [pscustomobject]@{ Accepted = $false; Reason = 'The downloaded Microsoft installer does not meet the supported SHA-256 integrity contract.'; Code = 'InvalidIntegrity' }
    }
    if (
        $Metadata.SignerName -ne $Policy.publisher -or
        $Metadata.SignerSubject -notmatch '(?:^|,\s*)O=Microsoft Corporation(?:,|$)'
    ) {
        return [pscustomobject]@{ Accepted = $false; Reason = 'The file is not signed by Microsoft Corporation.'; Code = 'WrongPublisher' }
    }
    if ($Metadata.OriginalFilename -ne $Policy.installerFileName) {
        return [pscustomobject]@{ Accepted = $false; Reason = 'The signed file is not the supported WebView2 Evergreen bootstrapper.'; Code = 'UnsupportedPayload' }
    }
    # The bootstrapper file version describes the bootstrapper itself, not the
    # Evergreen runtime it installs, so no minimum-version comparison applies
    # to the downloaded file. The authoritative check is the post-install
    # registry re-read of the runtime version against the policy minimum.
    return [pscustomobject]@{ Accepted = $true; Reason = 'Microsoft WebView2 bootstrapper publisher and SHA-256 integrity verified.'; Code = 'Verified' }
}

function Get-ProjectaWebView2BootstrapperMetadata {
    param([Parameter(Mandatory)][string]$Path)

    $attributes = [System.IO.File]::GetAttributes($Path)
    if (($attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'The Microsoft installer is a reparse point and cannot be verified safely.'
    }
    $initialHash = Get-ProjectaWebView2FileHash -Path $Path
    $signature = Get-ProjectaWebView2AuthenticodeSignature -Path $Path
    $version = [Diagnostics.FileVersionInfo]::GetVersionInfo($Path)
    $signerName = $null
    $signerSubject = $null
    if ($null -ne $signature.SignerCertificate) {
        $signerName = $signature.SignerCertificate.GetNameInfo(
            [System.Security.Cryptography.X509Certificates.X509NameType]::SimpleName,
            $false
        )
        $signerSubject = $signature.SignerCertificate.Subject
    }
    $verifiedHash = Get-ProjectaWebView2FileHash -Path $Path
    $attributesAfterVerification = [System.IO.File]::GetAttributes($Path)
    if (
        ($attributesAfterVerification -band [System.IO.FileAttributes]::ReparsePoint) -ne 0 -or
        -not (Test-ProjectaWebView2InstallerHash -Expected $initialHash -Actual $verifiedHash)
    ) {
        throw 'The Microsoft installer changed while its signature and metadata were being verified.'
    }
    return [pscustomobject]@{
        SignatureStatus = [string]$signature.Status
        SignerName = $signerName
        SignerSubject = $signerSubject
        OriginalFilename = $version.OriginalFilename
        ProductName = $version.ProductName
        FileVersion = $version.FileVersion
        Sha256 = $verifiedHash
    }
}

function Invoke-ProjectaWebView2BootstrapperDownload {
    param(
        [Parameter(Mandatory)][string]$Url,
        [Parameter(Mandatory)][string]$Destination
    )

    $request = [System.Net.HttpWebRequest]::Create([Uri]$Url)
    $request.Method = 'GET'
    $request.AllowAutoRedirect = $true
    $request.MaximumAutomaticRedirections = 5
    $request.Timeout = 120000
    $request.ReadWriteTimeout = 120000
    $response = $request.GetResponse()
    try {
        $finalUri = $response.ResponseUri
        if (
            $finalUri.Scheme -ne 'https' -or
            $finalUri.Host -notmatch '^(?:[a-z0-9-]+\.)*microsoft\.com$'
        ) {
            throw 'The official Microsoft download did not remain on HTTPS at a Microsoft host.'
        }
        if ($response.ContentLength -gt 150MB) {
            throw 'The Microsoft installer exceeded the permitted download size.'
        }
        $inputStream = $response.GetResponseStream()
        $outputStream = [System.IO.File]::Open(
            $Destination,
            [System.IO.FileMode]::CreateNew,
            [System.IO.FileAccess]::Write,
            [System.IO.FileShare]::None
        )
        try {
            $buffer = New-Object byte[] 65536
            $total = [long]0
            while (($count = $inputStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
                $total += $count
                if ($total -gt 150MB) { throw 'The Microsoft installer exceeded the permitted download size.' }
                $outputStream.Write($buffer, 0, $count)
            }
            if ($total -eq 0) { throw 'Microsoft returned an empty installer download.' }
        } finally {
            $outputStream.Dispose()
            $inputStream.Dispose()
        }
        return $finalUri.AbsoluteUri
    } finally {
        $response.Dispose()
    }
}

function Show-ProjectaWebView2Message {
    param(
        [Parameter(Mandatory)][string]$Text,
        [string]$Title = 'Projecta WebView2 prerequisite',
        [switch]$Question
    )

    try { Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop } catch {
        [Console]::Error.WriteLine($Text)
        return 'Unavailable'
    }
    if ($Question) {
        return [System.Windows.Forms.MessageBox]::Show(
            $Text, $Title,
            [System.Windows.Forms.MessageBoxButtons]::YesNo,
            [System.Windows.Forms.MessageBoxIcon]::Information
        )
    }
    [void][System.Windows.Forms.MessageBox]::Show(
        $Text, $Title,
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Warning
    )
    return [System.Windows.Forms.DialogResult]::OK
}

function Convert-ProjectaWebView2InstallerResult {
    param(
        [Parameter(Mandatory)][int]$ExitCode,
        [Parameter(Mandatory)][bool]$RuntimeReady
    )

    if ($ExitCode -eq 1602) { return 'Cancelled' }
    if ($ExitCode -in @(3010, 1641)) { return 'RestartRequired' }
    if ($ExitCode -ne 0) { return 'InstallerFailed' }
    if (-not $RuntimeReady) { return 'RuntimeNotReady' }
    return 'Ready'
}

function Ensure-ProjectaWebView2Runtime {
    param([Parameter(Mandatory)][string]$PolicyPath)

    $downloadPath = $null
    $env:PSModulePath = $PSHOME + '\Modules;' + $env:PSModulePath
    try {
        if (-not [Environment]::Is64BitOperatingSystem) {
            [void](Show-ProjectaWebView2Message 'Projecta requires Windows x64. No Projecta service or application was started.' )
            return 10
        }
        $policy = Get-Content -LiteralPath $PolicyPath -Raw -Encoding UTF8 | ConvertFrom-Json -ErrorAction Stop
        $minimum = ConvertTo-ProjectaWebView2Version $policy.minimumVersion
        if (
            $policy.formatVersion -ne 1 -or
            $policy.architecture -ne 'x64' -or
            $policy.sourceUrl -ne 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -or
            $policy.publisher -ne 'Microsoft Corporation' -or
            $policy.installerFileName -ne 'MicrosoftEdgeWebview2Setup.exe' -or
            $policy.integrityContract -ne 'sha256-of-authenticode-verified-download-rechecked-before-launch' -or
            $policy.runtimeGuid -ne '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}' -or
            $null -eq $minimum
        ) { throw 'The packaged WebView2 prerequisite policy is missing or unsupported.' }

        $installed = Get-ProjectaInstalledWebView2Runtime
        if (
            $null -ne $installed -and
            (Test-ProjectaInstalledWebView2Runtime -Versions $installed.AllVersions -MinimumVersion $policy.minimumVersion)
        ) {
            Write-Host "WebView2 prerequisite: skipped; Evergreen $($installed.Version) is already installed ($($installed.Source))."
            return 0
        }

        $answer = Show-ProjectaWebView2Message (
            "Projecta needs the Microsoft WebView2 Evergreen runtime, version $($policy.minimumVersion) or newer, before the desktop window can start. An installed Edge browser alone is not enough.`r`n`r`n" +
            "The installer will download the official Microsoft Evergreen bootstrapper directly over HTTPS from $($policy.sourceUrl). Internet access is required. The Microsoft installer displays its own license and consent screen and may request administrator approval; Projecta itself and its services remain installed and run per-user and are never elevated.`r`n`r`n" +
            'Choose Yes to download and verify the Microsoft installer. Choose No to cancel safely; Projecta will not launch and your workspace data will not be changed.'
        ) 'Microsoft WebView2 prerequisite' -Question
        if ($answer -ne [System.Windows.Forms.DialogResult]::Yes) {
            [void](Show-ProjectaWebView2Message 'Installation was canceled. Projecta did not start. To continue later, run Projecta again with Internet access and approve the Microsoft prerequisite if requested.' )
            return 23
        }

        $downloadPath = Join-Path ([System.IO.Path]::GetTempPath()) ("Projecta-webview2-setup-" + [guid]::NewGuid().ToString('N') + '.exe')
        [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
        try {
            $finalUrl = Invoke-ProjectaWebView2BootstrapperDownload -Url $policy.sourceUrl -Destination $downloadPath
        } catch {
            [void](Show-ProjectaWebView2Message (
                "The official Microsoft WebView2 installer could not be downloaded or the HTTPS connection was not accepted. Nothing was executed and Projecta did not start.`r`n`r`n" +
                "Check your Internet connection and retry later. Source: $($policy.sourceUrl)`r`n`r`nDetails: $($_.Exception.Message)"
            ))
            return 20
        }

        try { $metadata = Get-ProjectaWebView2BootstrapperMetadata -Path $downloadPath } catch {
            [void](Show-ProjectaWebView2Message "The downloaded prerequisite could not be inspected. It was not executed and Projecta did not start.")
            return 21
        }
        $verification = Test-ProjectaWebView2BootstrapperMetadata -Metadata $metadata -Policy $policy
        if (-not $verification.Accepted) {
            [void](Show-ProjectaWebView2Message (
                "$($verification.Reason) The downloaded file was not executed and Projecta did not start. Retry from a supported Microsoft download or contact the Projecta owner."
            ))
            return 21
        }
        Write-Host "WebView2 prerequisite: verified Microsoft signature, Evergreen bootstrapper $($metadata.FileVersion), SHA-256 $($metadata.Sha256); HTTPS source $finalUrl."

        try {
            $attributes = [System.IO.File]::GetAttributes($downloadPath)
            if (($attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw 'The verified download became a reparse point.'
            }
            $launchHash = Get-ProjectaWebView2FileHash -Path $downloadPath
        } catch {
            [void](Show-ProjectaWebView2Message 'The verified Microsoft installer changed or could not be checked immediately before execution. It was not run and Projecta did not start.')
            return 21
        }
        if (-not (Test-ProjectaWebView2InstallerHash -Expected $metadata.Sha256 -Actual $launchHash)) {
            [void](Show-ProjectaWebView2Message 'The Microsoft installer changed after signature verification. It was not run and Projecta did not start.')
            return 21
        }

        try {
            # Interactive install: no /silent flag, so the vendor consent UI is
            # authoritative. Projecta never silently installs the runtime.
            $process = Start-Process -FilePath $downloadPath -ArgumentList @('/install') -Wait -PassThru -ErrorAction Stop
        } catch {
            $nativeCode = $_.Exception.NativeErrorCode
            if ($nativeCode -eq 1223) {
                [void](Show-ProjectaWebView2Message 'The administrator approval request was canceled. Projecta did not start and no workspace data was changed.' )
                return 24
            }
            [void](Show-ProjectaWebView2Message "The verified Microsoft installer could not be started. Projecta did not start. Retry the installation or ask your administrator for help. Details: $($_.Exception.Message)" )
            return 27
        }
        $after = Get-ProjectaInstalledWebView2Runtime
        $afterVersions = @()
        if ($null -ne $after) { $afterVersions = $after.AllVersions }
        $outcome = Convert-ProjectaWebView2InstallerResult -ExitCode $process.ExitCode -RuntimeReady ([bool](Test-ProjectaInstalledWebView2Runtime -Versions $afterVersions -MinimumVersion $policy.minimumVersion))
        switch ($outcome) {
            'Ready' {
                Write-Host "WebView2 prerequisite: installed and rechecked; Evergreen $($after.Version) ($($after.Source))."
                return 0
            }
            'Cancelled' {
                [void](Show-ProjectaWebView2Message 'The Microsoft WebView2 installer was canceled. Projecta did not start. Run Projecta again to retry; existing workspace data is retained.' )
                return 25
            }
            'RestartRequired' {
                [void](Show-ProjectaWebView2Message 'Microsoft reports that Windows must be restarted to finish installing the WebView2 prerequisite. Projecta will not start now. Restart Windows yourself, then open Projecta again. This installer will not restart Windows automatically.' )
                return 26
            }
            'RuntimeNotReady' {
                [void](Show-ProjectaWebView2Message 'The Microsoft installer returned success, but the WebView2 Evergreen runtime is still missing or below the required version. Projecta did not start. Restart Windows if Microsoft requested it, then retry; otherwise contact the Projecta owner.' )
                return 28
            }
            default {
                [void](Show-ProjectaWebView2Message "The Microsoft WebView2 installer failed with exit code $($process.ExitCode). Projecta did not start. Retry or contact your administrator. Existing workspace data is retained." )
                return 27
            }
        }
    } catch {
        [void](Show-ProjectaWebView2Message "The Projecta prerequisite check failed safely. No Projecta application was started. Retry the installer or contact the Projecta owner. Details: $($_.Exception.Message)" )
        return 29
    } finally {
        if ($null -ne $downloadPath -and (Test-Path -LiteralPath $downloadPath -PathType Leaf)) {
            Remove-Item -LiteralPath $downloadPath -Force -ErrorAction SilentlyContinue
        }
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    $policyPath = Join-Path $PSScriptRoot 'webview2-runtime-policy.json'
    exit (Ensure-ProjectaWebView2Runtime -PolicyPath $policyPath)
}
