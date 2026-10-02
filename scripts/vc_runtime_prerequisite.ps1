function ConvertTo-ProjectaVcVersion {
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

function Test-ProjectaInstalledVcRuntime {
    param(
        [AllowNull()][object]$Record,
        [Parameter(Mandatory)][string]$MinimumVersion
    )

    if ($null -eq $Record -or $Record.Architecture -ne 'x64' -or [int]$Record.Installed -ne 1) {
        return $false
    }
    $installed = ConvertTo-ProjectaVcVersion $Record.Version
    $minimum = ConvertTo-ProjectaVcVersion $MinimumVersion
    if ($null -eq $installed -or $null -eq $minimum) { return $false }
    if (
        [int]$Record.Major -ne $installed.Major -or
        [int]$Record.Minor -ne $installed.Minor -or
        [int]$Record.Bld -ne $installed.Build -or
        [int]$Record.Rbld -ne $installed.Revision
    ) { return $false }
    return $installed -ge $minimum
}

function Get-ProjectaInstalledVcRuntime {
    $base = [Microsoft.Win32.RegistryKey]::OpenBaseKey(
        [Microsoft.Win32.RegistryHive]::LocalMachine,
        [Microsoft.Win32.RegistryView]::Registry64
    )
    try {
        $key = $base.OpenSubKey('SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64')
        if ($null -eq $key) { return $null }
        try {
            return [pscustomobject]@{
                Architecture = 'x64'
                Installed = $key.GetValue('Installed')
                Version = $key.GetValue('Version')
                Major = $key.GetValue('Major')
                Minor = $key.GetValue('Minor')
                Bld = $key.GetValue('Bld')
                Rbld = $key.GetValue('Rbld')
            }
        } finally {
            $key.Dispose()
        }
    } finally {
        $base.Dispose()
    }
}

function Test-ProjectaVcInstallerHash {
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

function Get-ProjectaVcFileHash {
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

function Get-ProjectaVcAuthenticodeSignature {
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


function Test-ProjectaVcRedistMetadata {
    param(
        [Parameter(Mandatory)][object]$Metadata,
        [Parameter(Mandatory)][object]$Policy
    )

    if ($Metadata.SignatureStatus -ne 'Valid') {
        return [pscustomobject]@{ Accepted = $false; Reason = 'The Microsoft Authenticode signature is invalid.'; Code = 'InvalidSignature' }
    }
    if (
        $Policy.integrityContract -ne 'sha256-of-authenticode-verified-download-rechecked-before-launch' -or
        -not (Test-ProjectaVcInstallerHash -Expected $Metadata.Sha256 -Actual $Metadata.Sha256)
    ) {
        return [pscustomobject]@{ Accepted = $false; Reason = 'The downloaded Microsoft installer does not meet the supported SHA-256 integrity contract.'; Code = 'InvalidIntegrity' }
    }
    if (
        $Metadata.SignerName -ne $Policy.publisher -or
        $Metadata.SignerSubject -notmatch '(?:^|,\s*)O=Microsoft Corporation(?:,|$)'
    ) {
        return [pscustomobject]@{ Accepted = $false; Reason = 'The file is not signed by Microsoft Corporation.'; Code = 'WrongPublisher' }
    }
    if (
        $Metadata.OriginalFilename -ne $Policy.installerFileName -or
        $Metadata.ProductName -notmatch '^Microsoft Visual C\+\+ .*Redistributable.*\(x64\)(?:\s+-\s+[0-9]+(?:\.[0-9]+){1,3})?$'
    ) {
        return [pscustomobject]@{ Accepted = $false; Reason = 'The signed file is not the supported x64 Visual C++ Redistributable.'; Code = 'UnsupportedPayload' }
    }
    $version = ConvertTo-ProjectaVcVersion $Metadata.FileVersion
    $minimum = ConvertTo-ProjectaVcVersion $Policy.minimumVersion
    if ($null -eq $version -or $null -eq $minimum -or $version -lt $minimum) {
        return [pscustomobject]@{ Accepted = $false; Reason = 'The signed Microsoft installer is older than the minimum compatible build.'; Code = 'UnsupportedVersion' }
    }
    return [pscustomobject]@{ Accepted = $true; Reason = 'Microsoft x64 Redistributable publisher, minimum version, and SHA-256 integrity verified.'; Code = 'Verified' }
}



function Get-ProjectaVcRedistMetadata {
    param([Parameter(Mandatory)][string]$Path)

    $attributes = [System.IO.File]::GetAttributes($Path)
    if (($attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'The Microsoft installer is a reparse point and cannot be verified safely.'
    }
    $initialHash = Get-ProjectaVcFileHash -Path $Path
    $signature = Get-ProjectaVcAuthenticodeSignature -Path $Path
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
    $verifiedHash = Get-ProjectaVcFileHash -Path $Path
    $attributesAfterVerification = [System.IO.File]::GetAttributes($Path)
    if (
        ($attributesAfterVerification -band [System.IO.FileAttributes]::ReparsePoint) -ne 0 -or
        -not (Test-ProjectaVcInstallerHash -Expected $initialHash -Actual $verifiedHash)
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



function Invoke-ProjectaVcRedistDownload {
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

function Show-ProjectaVcMessage {
    param(
        [Parameter(Mandatory)][string]$Text,
        [string]$Title = 'Projecta Visual C++ prerequisite',
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

function Convert-ProjectaVcInstallerResult {
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

function Ensure-ProjectaVcRuntime {
    param([Parameter(Mandatory)][string]$PolicyPath)

    $downloadPath = $null
    $env:PSModulePath = $PSHOME + '\Modules;' + $env:PSModulePath
    try {
        if (-not [Environment]::Is64BitOperatingSystem) {
            [void](Show-ProjectaVcMessage 'Projecta requires Windows x64. No Projecta service or application was started.' )
            return 10
        }
        $policy = Get-Content -LiteralPath $PolicyPath -Raw -Encoding UTF8 | ConvertFrom-Json -ErrorAction Stop
        $minimum = ConvertTo-ProjectaVcVersion $policy.minimumVersion
        if (
            $policy.formatVersion -ne 1 -or
            $policy.architecture -ne 'x64' -or
            $policy.sourceUrl -ne 'https://aka.ms/vc14/vc_redist.x64.exe' -or
            $policy.publisher -ne 'Microsoft Corporation' -or
            $policy.installerFileName -ne 'VC_redist.x64.exe' -or
            $policy.integrityContract -ne 'sha256-of-authenticode-verified-download-rechecked-before-launch' -or
            $null -eq $minimum
        ) { throw 'The packaged Visual C++ prerequisite policy is missing or unsupported.' }


        $installed = Get-ProjectaInstalledVcRuntime
        if (Test-ProjectaInstalledVcRuntime -Record $installed -MinimumVersion $policy.minimumVersion) {
            $version = ConvertTo-ProjectaVcVersion $installed.Version
            Write-Host "VC++ prerequisite: skipped; x64 v14 $version is already installed."
            return 0
        }

        $answer = Show-ProjectaVcMessage (
            "Projecta needs the Microsoft x64 Visual C++ v14 runtime, version $($policy.minimumVersion) or newer, before any Projecta application or Python runtime can start.`r`n`r`n" +
            "The installer will download the official Microsoft package directly over HTTPS from $($policy.sourceUrl). Internet access is required. The Microsoft installer will request administrator approval through UAC and display its own license and consent screen. Projecta itself and its services remain installed and run per-user; they will not be elevated.`r`n`r`n" +
            'Choose Yes to download and verify the Microsoft installer. Choose No to cancel safely; Projecta will not launch and your workspace data will not be changed.'
        ) 'Microsoft Visual C++ prerequisite' -Question
        if ($answer -ne [System.Windows.Forms.DialogResult]::Yes) {
            [void](Show-ProjectaVcMessage 'Installation was canceled. Projecta did not start. To continue later, run Projecta again with Internet access and approve the Microsoft prerequisite if requested.' )
            return 23
        }

        $downloadPath = Join-Path ([System.IO.Path]::GetTempPath()) ("Projecta-vc-redist-" + [guid]::NewGuid().ToString('N') + '.exe')
        [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
        try {
            $finalUrl = Invoke-ProjectaVcRedistDownload -Url $policy.sourceUrl -Destination $downloadPath
        } catch {
            [void](Show-ProjectaVcMessage (
                "The official Microsoft Visual C++ installer could not be downloaded or the HTTPS connection was not accepted. Nothing was executed and Projecta did not start.`r`n`r`n" +
                "Check your Internet connection and retry later. Source: $($policy.sourceUrl)`r`n`r`nDetails: $($_.Exception.Message)"
            ))
            return 20
        }

        try { $metadata = Get-ProjectaVcRedistMetadata -Path $downloadPath } catch {
            [void](Show-ProjectaVcMessage "The downloaded prerequisite could not be inspected. It was not executed and Projecta did not start.")
            return 21
        }
        $verification = Test-ProjectaVcRedistMetadata -Metadata $metadata -Policy $policy
        if (-not $verification.Accepted) {
            $code = if ($verification.Code -eq 'UnsupportedVersion') { 22 } else { 21 }
            [void](Show-ProjectaVcMessage (
                "$($verification.Reason) The downloaded file was not executed and Projecta did not start. Retry from a supported Microsoft download or contact the Projecta owner."
            ))
            return $code
        }
        Write-Host "VC++ prerequisite: verified Microsoft signature, x64 product, file version $($metadata.FileVersion), SHA-256 $($metadata.Sha256); HTTPS source $finalUrl."

        try {
            $attributes = [System.IO.File]::GetAttributes($downloadPath)
            if (($attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw 'The verified download became a reparse point.'
            }
            $launchHash = Get-ProjectaVcFileHash -Path $downloadPath
        } catch {
            [void](Show-ProjectaVcMessage 'The verified Microsoft installer changed or could not be checked immediately before execution. It was not run and Projecta did not start.')
            return 21
        }
        if (-not (Test-ProjectaVcInstallerHash -Expected $metadata.Sha256 -Actual $launchHash)) {
            [void](Show-ProjectaVcMessage 'The Microsoft installer changed after signature verification. It was not run and Projecta did not start.')
            return 21
        }

        try {
            $process = Start-Process -FilePath $downloadPath -ArgumentList @('/install', '/norestart') -Verb RunAs -Wait -PassThru -ErrorAction Stop
        } catch {
            $nativeCode = $_.Exception.NativeErrorCode
            if ($nativeCode -eq 1223) {
                [void](Show-ProjectaVcMessage 'The administrator approval request was canceled. Projecta did not start and no workspace data was changed.' )
                return 24
            }
            [void](Show-ProjectaVcMessage "The verified Microsoft installer could not be started with administrator approval. Projecta did not start. Retry the installation or ask your administrator for help. Details: $($_.Exception.Message)" )
            return 27
        }
        $after = Get-ProjectaInstalledVcRuntime
        $outcome = Convert-ProjectaVcInstallerResult -ExitCode $process.ExitCode -RuntimeReady ([bool](Test-ProjectaInstalledVcRuntime -Record $after -MinimumVersion $policy.minimumVersion))
        switch ($outcome) {
            'Ready' {
                Write-Host "VC++ prerequisite: installed and rechecked; x64 v14 $($after.Version)."
                return 0
            }
            'Cancelled' {
                [void](Show-ProjectaVcMessage 'The Microsoft Visual C++ installer was canceled. Projecta did not start. Run Projecta again to retry; existing workspace data is retained.' )
                return 25
            }
            'RestartRequired' {
                [void](Show-ProjectaVcMessage 'Microsoft reports that Windows must be restarted to finish installing the Visual C++ prerequisite. Projecta will not start now. Restart Windows yourself, then open Projecta again. This installer will not restart Windows automatically.' )
                return 26
            }
            'RuntimeNotReady' {
                [void](Show-ProjectaVcMessage 'The Microsoft installer returned success, but the x64 Visual C++ runtime is still missing or below the required version. Projecta did not start. Restart Windows if Microsoft requested it, then retry; otherwise contact the Projecta owner.' )
                return 28
            }
            default {
                [void](Show-ProjectaVcMessage "The Microsoft Visual C++ installer failed with exit code $($process.ExitCode). Projecta did not start. Retry or contact your administrator. Existing workspace data is retained." )
                return 27
            }
        }
    } catch {
        [void](Show-ProjectaVcMessage "The Projecta prerequisite check failed safely. No Projecta application was started. Retry the installer or contact the Projecta owner. Details: $($_.Exception.Message)" )
        return 29
    } finally {
        if ($null -ne $downloadPath -and (Test-Path -LiteralPath $downloadPath -PathType Leaf)) {
            Remove-Item -LiteralPath $downloadPath -Force -ErrorAction SilentlyContinue
        }
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    $policyPath = Join-Path $PSScriptRoot 'vc-runtime-policy.json'
    exit (Ensure-ProjectaVcRuntime -PolicyPath $policyPath)
}
