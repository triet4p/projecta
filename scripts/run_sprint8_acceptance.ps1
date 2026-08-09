param(
    [switch]$RunCompose,
    [switch]$RunRealBrowser,
    [switch]$KeepStack,
    [string]$ComposeProject = "projecta-sprint8-$([guid]::NewGuid().ToString('N').Substring(0, 12))",
    [int]$StartupTimeoutSeconds = 240
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$environmentNames = @(
    "PROJECTA_API_TRUSTED_CONTEXT_SECRET",
    "PROJECTA_API_SECRET_STORE_MASTER_KEY",
    "PROJECTA_API_RUNTIME_MODE",
    "PROJECTA_API_EXPERIENCE_ACTOR_ID",
    "PROJECTA_API_EXPERIENCE_PROJECT_CATALOG",
    "PROJECTA_LLM_TYPE",
    "PROJECTA_LLM_BASE_URL",
    "PROJECTA_LLM_API_KEY",
    "PROJECTA_LLM_MODEL",
    "PROJECTA_BOOTSTRAP_ACCEPTANCE_PROJECTS"
)
$previousEnvironment = @{}

function Set-ValidationEnvironment {
    $bytes = New-Object byte[] 32
    $random = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $random.GetBytes($bytes) }
    finally { $random.Dispose() }
    $trustedSecret = [Convert]::ToBase64String($bytes)
    $masterKey = uv run --project (Join-Path $root "apps/api") python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    if ($LASTEXITCODE -ne 0) { throw "Could not generate the validation-only secret-store key." }

    $values = @{
        PROJECTA_API_TRUSTED_CONTEXT_SECRET = $trustedSecret
        PROJECTA_API_SECRET_STORE_MASTER_KEY = $masterKey.Trim()
        PROJECTA_API_RUNTIME_MODE = "experience"
        PROJECTA_API_EXPERIENCE_ACTOR_ID = "acceptance-reviewer"
        PROJECTA_API_EXPERIENCE_PROJECT_CATALOG = "project-alpha,project-beta"
        PROJECTA_LLM_TYPE = ""
        PROJECTA_LLM_BASE_URL = ""
        PROJECTA_LLM_API_KEY = ""
        PROJECTA_LLM_MODEL = ""
        PROJECTA_BOOTSTRAP_ACCEPTANCE_PROJECTS = "project-alpha|Project Alpha;project-beta|Project Beta"
    }
    foreach ($name in $environmentNames) {
        $path = "Env:$name"
        $previousEnvironment[$name] = @{ Exists = Test-Path $path; Value = if (Test-Path $path) { (Get-Item $path).Value } else { $null } }
        Set-Item -Path $path -Value $values[$name]
    }
}

function Restore-ValidationEnvironment {
    foreach ($name in $environmentNames) {
        $previous = $previousEnvironment[$name]
        if ($null -eq $previous) { continue }
        if ($previous.Exists) { Set-Item -Path "Env:$name" -Value $previous.Value }
        else { Remove-Item -Path "Env:$name" -ErrorAction SilentlyContinue }
    }
}

function Invoke-Checked([string]$Label, [scriptblock]$Command) {
    Write-Host "[S8-65] $Label"
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$Label failed with exit code $LASTEXITCODE." }
}

function Wait-WebReady([string]$Url, [string]$Label) {
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

function Assert-SafeComposeLogs {
    $logs = docker compose -p $ComposeProject --profile web logs --no-color --timestamps 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) { throw "Could not collect correlated Compose logs." }
    $forbidden = @(
        $env:PROJECTA_API_TRUSTED_CONTEXT_SECRET,
        $env:PROJECTA_API_SECRET_STORE_MASTER_KEY,
        "X-Projecta-Context-Secret",
        "secretReference",
        "apiKey",
        "https://w3id.org/projecta/"
    ) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    foreach ($value in $forbidden) {
        if ($logs.Contains($value)) { throw "Compose logs leaked a forbidden secret/internal value." }
    }
    if ($logs -notmatch "requestId|operationId|correlation") {
        throw "Compose logs did not expose a correlation field."
    }
}

Push-Location $root
try {
    Set-ValidationEnvironment
    Invoke-Checked "Compose health contract" { & (Join-Path $root "scripts/check_sprint8_health_contract.ps1") }
    Invoke-Checked "Compose interpolation and authority-default check" {
        $config = docker compose -p $ComposeProject --profile web config
        if ($LASTEXITCODE -ne 0) { throw "Compose interpolation failed." }
        if ($config -match "local-project|local-user") { throw "Compose contains an authority-bearing local default." }
    }

    if (-not $RunCompose) {
        Write-Output "Sprint 8 Compose acceptance preflight passed. Use -RunCompose for clean-volume runtime acceptance."
        return
    }

    Invoke-Checked "Clean-volume production web stack startup" { docker compose -p $ComposeProject --profile web up -d --build }
    Wait-WebReady "http://127.0.0.1:3000/health/live" "production web liveness"
    Wait-WebReady "http://127.0.0.1:3000/health/ready" "production web readiness"
    docker compose -p $ComposeProject --profile web ps
    Assert-SafeComposeLogs

    Invoke-Checked "API/web restart persistence check" { docker compose -p $ComposeProject restart api web }
    Wait-WebReady "http://127.0.0.1:3000/health/ready" "post-restart readiness"
    Assert-SafeComposeLogs

    if ($RunRealBrowser) {
        Invoke-Checked "Real browser acceptance through production web image" { npm --prefix apps/web run test:e2e:real }
    } else {
        Write-Output "Runtime Compose checks passed. Real browser acceptance was not requested; use -RunRealBrowser only with a configured replay/experience fixture."
    }
}
finally {
    if ($RunCompose -and -not $KeepStack) {
        docker compose -p $ComposeProject --profile web down --volumes --remove-orphans
    }
    Restore-ValidationEnvironment
    Pop-Location
}
