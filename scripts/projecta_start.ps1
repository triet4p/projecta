[CmdletBinding()]
param([switch]$InstallOnly)

$ErrorActionPreference = 'Stop'
$prerequisiteScript = Join-Path $PSScriptRoot 'runtime\vc_runtime_prerequisite.ps1'
try {
    . $prerequisiteScript
    $policyPath = Join-Path $PSScriptRoot 'runtime\vc-runtime-policy.json'
    $result = Ensure-ProjectaVcRuntime -PolicyPath $policyPath
    if ($result -ne 0) { exit $result }
    if ($InstallOnly) {
        Write-Host 'VC++ prerequisite ready; no Projecta application was started.'
        exit 0
    }
    $application = Join-Path $PSScriptRoot 'Projecta.exe'
    if (-not (Test-Path -LiteralPath $application -PathType Leaf)) {
        throw 'The Projecta desktop application is missing from the installation.'
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
