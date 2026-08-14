param(
    [string]$ComposeProject = "projecta-s10-acceptance-$([guid]::NewGuid().ToString('N').Substring(0, 12))",
    [int]$StartupTimeoutSeconds = 300
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$savedEnvironment = @{}
$environment = @{
    PROJECTA_API_TRUSTED_CONTEXT_SECRET = "s10-acceptance-trusted-context"
    PROJECTA_API_SECRET_STORE_MASTER_KEY = $null
    PROJECTA_API_RUNTIME_MODE = "experience"
    PROJECTA_API_EXPERIENCE_ACTOR_ID = "acceptance-reviewer"
    PROJECTA_API_EXPERIENCE_PROJECT_CATALOG = "project-a,project-b"
    PROJECTA_CONNECTOR_LOCAL_ADMIN_ENABLED = "true"
    PROJECTA_BOOTSTRAP_ACCEPTANCE_PROJECTS = "project-a|Project A;project-b|Project B"
    PROJECTA_LLM_TYPE = ""
    PROJECTA_LLM_BASE_URL = ""
    PROJECTA_LLM_API_KEY = ""
    PROJECTA_LLM_MODEL = ""
    PROJECTA_CONNECTOR_POSTGRES_USER = "connector_acceptance"
    PROJECTA_CONNECTOR_POSTGRES_PASSWORD = "s10-acceptance-password"
    PROJECTA_CONNECTOR_POSTGRES_DB = "projecta_acceptance"
}
$stackStarted = $false
$firstFailure = $null
$hostTestEnvironment = @{}

function Set-Environment {
    $masterKeyBytes = New-Object byte[] 32
    $random = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $random.GetBytes($masterKeyBytes) }
    finally { $random.Dispose() }
    $environment.PROJECTA_API_SECRET_STORE_MASTER_KEY = [Convert]::ToBase64String($masterKeyBytes).Replace('+', '-').Replace('/', '_')
    foreach ($entry in $environment.GetEnumerator()) {
        $path = "Env:$($entry.Key)"
        $savedEnvironment[$entry.Key] = @{
            Exists = Test-Path $path
            Value = if (Test-Path $path) { (Get-Item $path).Value } else { $null }
        }
        Set-Item -Path $path -Value $entry.Value
    }
}

function Restore-Environment {
    foreach ($entry in $savedEnvironment.GetEnumerator()) {
        $path = "Env:$($entry.Key)"
        if ($entry.Value.Exists) { Set-Item -Path $path -Value $entry.Value.Value }
        else { Remove-Item -Path $path -ErrorAction SilentlyContinue }
    }
}

function Enter-HostTestEnvironment {
    foreach ($entry in $environment.GetEnumerator()) {
        $path = "Env:$($entry.Key)"
        $hostTestEnvironment[$entry.Key] = @{
            Exists = Test-Path $path
            Value = if (Test-Path $path) { (Get-Item $path).Value } else { $null }
        }
        Remove-Item -Path $path -ErrorAction SilentlyContinue
    }
}

function Exit-HostTestEnvironment {
    foreach ($entry in $hostTestEnvironment.GetEnumerator()) {
        $path = "Env:$($entry.Key)"
        if ($entry.Value.Exists) { Set-Item -Path $path -Value $entry.Value.Value }
        else { Remove-Item -Path $path -ErrorAction SilentlyContinue }
    }
    $hostTestEnvironment.Clear()
}

function Invoke-Checked([string]$Label, [scriptblock]$Command) {
    Write-Host "[S10-62] $Label"
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$Label failed with exit code $LASTEXITCODE." }
}

function Wait-Ready([string]$Url, [string]$Label) {
    $deadline = (Get-Date).AddSeconds($StartupTimeoutSeconds)
    do {
        try {
            $response = Invoke-WebRequest -UseBasicParsing $Url
            if ($response.StatusCode -eq 200) { return }
        } catch { }
        if ((Get-Date) -gt $deadline) { throw "$Label timed out." }
        Start-Sleep -Seconds 3
    } while ($true)
}

function Assert-SafeLogs {
    $logs = docker compose -p $ComposeProject --profile web logs --no-color --timestamps 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) { throw "Could not collect Compose logs." }
    $forbiddenValues = @(
        @{ Label = "trusted context secret"; Value = $environment.PROJECTA_API_TRUSTED_CONTEXT_SECRET },
        @{ Label = "master key"; Value = $environment.PROJECTA_API_SECRET_STORE_MASTER_KEY },
        @{ Label = "secretReference field"; Value = "secretReference" },
        @{ Label = "ontology IRI"; Value = "https://w3id.org/projecta/" },
        @{ Label = "fixture payload"; Value = "fixture://project-a/message-001" }
    )
    foreach ($forbidden in $forbiddenValues) {
        if ($logs.Contains($forbidden.Value)) {
            $service = "unknown service"
            foreach ($candidate in @("api", "semantic-core", "web", "postgres", "fuseki")) {
                $serviceLogs = docker compose -p $ComposeProject --profile web logs --no-color --timestamps $candidate 2>&1 | Out-String
                if ($LASTEXITCODE -ne 0) { throw "Could not collect Compose logs for $candidate." }
                if ($serviceLogs.Contains($forbidden.Value)) { $service = $candidate; break }
            }
            throw "Compose logs leaked a forbidden value category: $($forbidden.Label) ($service)."
        }
    }
    if ($logs -notmatch "requestId=.*operationId=|requestId.*operationId") {
        throw "Compose logs did not contain correlated operation fields."
    }
}

Push-Location $root
try {
    Set-Environment
    Invoke-Checked "Compose interpolation" { docker compose -p $ComposeProject --profile web config --quiet }
    Invoke-Checked "Build local Fuseki bootstrap image" { docker compose -p $ComposeProject --profile web build fuseki }
    Invoke-Checked "Clean production-shaped stack startup" { docker compose -p $ComposeProject --profile web up -d --build }
    $stackStarted = $true
    Wait-Ready "http://127.0.0.1:3000/health/live" "web liveness"
    Wait-Ready "http://127.0.0.1:3000/health/ready" "web readiness"

    Invoke-Checked "Journey 1 authorized import and Journey 7 accessible operation" {
        Push-Location (Join-Path $root "apps/web")
        $savedNoColor = if (Test-Path Env:NO_COLOR) { (Get-Item Env:NO_COLOR).Value } else { $null }
        try {
            Remove-Item Env:NO_COLOR -ErrorAction SilentlyContinue
            npx playwright test --config=playwright.real.config.ts --workers=1 sprint7.real.spec.ts sprint10.real.spec.ts
        }
        finally {
            if ($null -ne $savedNoColor) { Set-Item Env:NO_COLOR $savedNoColor }
            Pop-Location
        }
    }
    Enter-HostTestEnvironment
    try {
        Invoke-Checked "Journey 2 evidence lifecycle" {
            uv run --project apps/api pytest -q apps/api/tests/test_connector_source_mapping.py apps/api/tests/test_connector_evidence.py
        }
        Invoke-Checked "Journey 3 idempotent replay" {
            uv run --project apps/api pytest -q apps/api/tests/test_connector_kernel.py -k "single_attempt or replay"
        }
        Invoke-Checked "Journey 4 project isolation" {
            uv run --project apps/api pytest -q apps/api/tests/test_connector_authorization.py apps/api/tests/test_connector_public_api.py
        }
        Invoke-Checked "Journey 5 failure truthfulness" {
            uv run --project apps/api pytest -q apps/api/tests/test_connector_kernel.py -k "failure or rollback"
        }
        Invoke-Checked "Journey 6 recovery" {
            python -m unittest scripts.tests.test_sprint10_recovery_contract
        }
    } finally {
        Exit-HostTestEnvironment
    }
    Assert-SafeLogs

    Invoke-Checked "Restart API, web, and PostgreSQL" {
        docker compose -p $ComposeProject restart api web connector-postgres
    }
    Wait-Ready "http://127.0.0.1:3000/health/ready" "post-restart web readiness"
    Invoke-Checked "Journey 6 post-restart persistence through the production web image" {
        Push-Location (Join-Path $root "apps/web")
        $savedNoColor = if (Test-Path Env:NO_COLOR) { (Get-Item Env:NO_COLOR).Value } else { $null }
        try {
            Remove-Item Env:NO_COLOR -ErrorAction SilentlyContinue
            npx playwright test --config=playwright.real.config.ts --workers=1 sprint10.restart.real.spec.ts
        }
        finally {
            if ($null -ne $savedNoColor) { Set-Item Env:NO_COLOR $savedNoColor }
            Pop-Location
        }
    }
    Assert-SafeLogs
    Write-Host "Sprint 10 clean-Compose acceptance passed."
} catch {
    $firstFailure = $_.Exception.Message
    if ($stackStarted) {
        docker compose -p $ComposeProject logs --no-color api semantic-core | Out-Host
    }
    Write-Error $firstFailure
    exit 1
} finally {
    if ($stackStarted) {
        docker compose -p $ComposeProject --profile web down --volumes --remove-orphans | Out-Host
    }
    Restore-Environment
    Pop-Location
}
