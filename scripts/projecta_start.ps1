[CmdletBinding()]
param([switch]$InstallOnly)

$ErrorActionPreference = 'Stop'
try {
    # WebView2 first: the Tauri window cannot render without the Evergreen
    # runtime. VC++ second: the bundled backend cannot start without it.
    # Either gate stops safely (nonzero exit, nothing started) on installed-
    # missing/declined/failed/restart-required paths; only a disclosed vendor
    # installer may elevate.
    $webview2Script = Join-Path $PSScriptRoot 'runtime\webview2_runtime_prerequisite.ps1'
    . $webview2Script
    $webview2Policy = Join-Path $PSScriptRoot 'runtime\webview2-runtime-policy.json'
    $result = Ensure-ProjectaWebView2Runtime -PolicyPath $webview2Policy
    if ($result -ne 0) { exit $result }
    $vcScript = Join-Path $PSScriptRoot 'runtime\vc_runtime_prerequisite.ps1'
    . $vcScript
    $vcPolicy = Join-Path $PSScriptRoot 'runtime\vc-runtime-policy.json'
    $result = Ensure-ProjectaVcRuntime -PolicyPath $vcPolicy
    if ($result -ne 0) { exit $result }
    if ($InstallOnly) {
        Write-Host 'Prerequisites ready (WebView2 + VC++); no Projecta application was started.'
        exit 0
    }
    $application = Join-Path $PSScriptRoot 'Projecta.exe'
    if (-not (Test-Path -LiteralPath $application -PathType Leaf)) {
        throw 'The Projecta Tauri desktop application is missing from the installation.'
    }
    Start-Process -FilePath $application -WorkingDirectory $PSScriptRoot -ErrorAction Stop
    exit 0
} catch {
    try {
        Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop
        [void][System.Windows.Forms.MessageBox]::Show(
            "Projecta could not start. Its installed files were left unchanged. Retry the installer or contact the Projecta owner.`r`n`r`nDetails: $($_.Exception.Message)",
            'Projecta could not start',
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Error
        )
    } catch {
        [Console]::Error.WriteLine("Projecta could not start safely: $($_.Exception.Message)")
    }
    exit 29
}
