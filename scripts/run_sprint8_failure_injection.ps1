param(
    [switch]$RunCompose
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Invoke-Checked([string]$Label, [scriptblock]$Command, [string]$WorkingDirectory = $root) {
    Push-Location $WorkingDirectory
    try {
        Write-Host "[S8-25] $Label"
        & $Command
        if ($LASTEXITCODE -ne 0) {
            throw "$Label failed with exit code $LASTEXITCODE."
        }
    } finally {
        Pop-Location
    }
}

Invoke-Checked "API provider/Core/crash failure matrix" {
    uv run pytest -q tests/test_sprint8_failure_injection.py
} (Join-Path $root "apps/api")

Invoke-Checked "API failure-matrix lint" {
    uv run ruff check src/projecta_api/main.py tests/test_sprint8_failure_injection.py
} (Join-Path $root "apps/api")

Invoke-Checked "Semantic Core/Fuseki failure injection" {
    mvn --batch-mode "-Dspotless.check.skip=true" -Dtest=FusekiGatewayTest test
} (Join-Path $root "services/semantic-core")

Invoke-Checked "Nginx upstream timeout/log contract" {
    npm run check:nginx-config
} (Join-Path $root "apps/web")

if ($RunCompose) {
    Invoke-Checked "Canonical Compose cross-container smoke harness" {
        & (Join-Path $root "scripts/run_system_tests.ps1")
    }
}

Write-Output "Sprint 8 failure-injection matrix passed: one terminal error and no semantic mutation assertions are green."
