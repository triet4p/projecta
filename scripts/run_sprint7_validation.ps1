$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$apiRoot = (Resolve-Path (Join-Path $root "apps/api")).Path
Push-Location $root
try {
    function Invoke-CheckedCommand {
        param(
            [Parameter(Mandatory = $true)][string]$FilePath,
            [Parameter(Mandatory = $false)][string[]]$Arguments = @(),
            [Parameter(Mandatory = $false)][string]$WorkingDirectory = $root
        )
        Push-Location $WorkingDirectory
        try {
            & $FilePath @Arguments
            if ($LASTEXITCODE -ne 0) {
                throw "$FilePath $($Arguments -join ' ') failed with exit code $LASTEXITCODE."
            }
        } finally {
            Pop-Location
        }
    }

    Invoke-CheckedCommand uv @("run", "ruff", "check", ".") $apiRoot
    Invoke-CheckedCommand uv @("run", "pyright") $apiRoot
    Invoke-CheckedCommand uv @("run", "pytest", "-q") $apiRoot
    Invoke-CheckedCommand npm @("--prefix", "apps/web", "run", "format:check")
    Invoke-CheckedCommand npm @("--prefix", "apps/web", "run", "typecheck")
    Invoke-CheckedCommand npm @("--prefix", "apps/web", "run", "lint")
    Invoke-CheckedCommand npm @("--prefix", "apps/web", "run", "test")
    Invoke-CheckedCommand npm @("--prefix", "apps/web", "run", "check:nginx-config")
    Invoke-CheckedCommand npm @("--prefix", "apps/web", "run", "check:api-drift")
    Invoke-CheckedCommand npm @("--prefix", "apps/web", "run", "build")
    Write-Host "Configured Sprint 7 API and frontend validation commands completed."
    Write-Host "Docker image and clean Compose acceptance remain environment-dependent; use run_sprint7_acceptance.ps1 when Docker is available."
} finally {
    Pop-Location
}
