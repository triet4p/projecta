param(
    [string]$ComposeProject = "projecta-sprint7-$([guid]::NewGuid().ToString('N'))",
    [int]$StartupTimeoutSeconds = 180
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$trustedSecret = if ($env:PROJECTA_API_TRUSTED_CONTEXT_SECRET) {
    $env:PROJECTA_API_TRUSTED_CONTEXT_SECRET
} else {
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    [Convert]::ToBase64String($bytes)
}
$masterKey = if ($env:PROJECTA_API_SECRET_STORE_MASTER_KEY) {
    $env:PROJECTA_API_SECRET_STORE_MASTER_KEY
} else {
    (uv run --project apps/api python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
}
$env:PROJECTA_API_TRUSTED_CONTEXT_SECRET = $trustedSecret
$env:PROJECTA_API_SECRET_STORE_MASTER_KEY = $masterKey
$env:PROJECTA_API_RUNTIME_MODE = "experience"
$env:PROJECTA_LLM_TYPE = ""
$env:PROJECTA_LLM_BASE_URL = ""
$env:PROJECTA_LLM_API_KEY = ""
$env:PROJECTA_LLM_MODEL = ""

Push-Location $root
try {
    docker compose -p $ComposeProject --profile web up -d --build
    $deadline = (Get-Date).AddSeconds($StartupTimeoutSeconds)
    do {
        try {
            $response = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:3000/health/live"
            if ($response.StatusCode -eq 200) { break }
        } catch { }
        if ((Get-Date) -gt $deadline) { throw "Sprint 7 Compose web health check timed out." }
        Start-Sleep -Seconds 3
    } while ($true)

    docker compose -p $ComposeProject --profile web ps
    Write-Host "Web/API/Semantic Core/Fuseki are healthy enough for browser acceptance."
    npm --prefix apps/web run test:e2e:real
    if ($LASTEXITCODE -ne 0) { throw "Real-stack browser acceptance failed before restart." }

    docker compose -p $ComposeProject restart api web
    docker compose -p $ComposeProject --profile web ps
    $restartDeadline = (Get-Date).AddSeconds($StartupTimeoutSeconds)
    do {
        try {
            $ready = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:3000/health/ready"
            if ($ready.StatusCode -eq 200) { break }
        } catch { }
        if ((Get-Date) -gt $restartDeadline) { throw "Sprint 7 readiness check timed out after restart." }
        Start-Sleep -Seconds 3
    } while ($true)
    npm --prefix apps/web run test:e2e:real
    if ($LASTEXITCODE -ne 0) { throw "Real-stack browser acceptance failed after restart." }
} finally {
    docker compose -p $ComposeProject --profile web down --volumes --remove-orphans
    Pop-Location
}
