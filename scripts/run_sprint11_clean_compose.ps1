param(
    [switch]$AllowDirtyWorktree,
    [switch]$Start,
    [switch]$ConfigOnly,
    [string]$EvidencePath = "docs/sprint-plans/sprint-11/artifacts/s11-66-clean-compose.json"
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$project = "projecta-s11-accept-$([guid]::NewGuid().ToString('N').Substring(0, 12))"
$evidence = Join-Path $root $EvidencePath
$operatorRoot = Join-Path ([System.IO.Path]::GetTempPath()) $project
$recoveryRoot = Join-Path $operatorRoot "recovery"
$roleIdFile = Join-Path $operatorRoot "role-id"
$secretIdFile = Join-Path $operatorRoot "secret-id"
$results = [System.Collections.Generic.List[object]]::new()
$startedAt = [DateTime]::UtcNow
$status = "failed"
$failure = $null
$started = $false

function Invoke-Compose {
    param([Parameter(Mandatory = $true)][string]$Name, [string[]]$Arguments, [switch]$Sensitive)
    $gateStarted = [DateTime]::UtcNow
    $output = @(& docker compose -p $project -f (Join-Path $root "compose.yaml") -f (Join-Path $root "compose.prod.yaml") @Arguments 2>&1 | ForEach-Object { [string]$_ })
    $exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { [int]$LASTEXITCODE }
    $safeOutput = if ($Sensitive) { @("<operator-sensitive output redacted>") } else { @($output | Select-Object -Last 100) }
    $results.Add([pscustomobject]@{ name = $Name; exitCode = $exitCode; startedAt = $gateStarted.ToString("o"); finishedAt = [DateTime]::UtcNow.ToString("o"); output = $safeOutput })
    if (-not $Sensitive) { $output | Select-Object -Last 12 | ForEach-Object { Write-Host $_ } }
    if ($exitCode -ne 0) { throw "$Name failed with exit code $exitCode." }
    return $output
}

function Assert-OperatorInput {
    foreach ($relative in @(
        "infra/openbao/tls/ca.crt", "infra/openbao/tls/tls.crt", "infra/openbao/tls/tls.key",
        "infra/keycloak/tls/ca.crt", "infra/keycloak/tls/tls.crt", "infra/keycloak/tls/tls.key",
        "infra/edge/tls/projecta.crt", "infra/edge/tls/projecta.key", "infra/edge/tls/auth.crt", "infra/edge/tls/auth.key"
    )) {
        if (-not (Test-Path -LiteralPath (Join-Path $root $relative) -PathType Leaf)) {
            throw "Missing untracked TLS input: $relative"
        }
    }
    foreach ($name in @("CONNECTOR_POSTGRES_IMAGE", "KEYCLOAK_IMAGE", "OPENBAO_IMAGE", "EDGE_IMAGE", "API_IMAGE", "WEB_IMAGE", "SEMANTIC_CORE_IMAGE")) {
        $value = [Environment]::GetEnvironmentVariable($name)
        if ([string]::IsNullOrWhiteSpace($value) -or $value -notmatch '@sha256:[0-9a-f]{64}$') {
            throw "$name must be an immutable sha256 image reference."
        }
    }
}

try {
    if (-not $AllowDirtyWorktree -and @(git -C $root status --porcelain).Count -gt 0) {
        throw "Clean-Compose acceptance requires a clean worktree."
    }
    New-Item -ItemType Directory -Path $recoveryRoot -Force | Out-Null
    Set-Content -LiteralPath $roleIdFile -Value "bootstrap-pending" -NoNewline
    Set-Content -LiteralPath $secretIdFile -Value "bootstrap-pending" -NoNewline
    $env:PROJECTA_OPENBAO_ROLE_ID_FILE = $roleIdFile
    $env:PROJECTA_OPENBAO_SECRET_ID_FILE = $secretIdFile

    Invoke-Compose "Production Compose interpolation" @("config", "--quiet") | Out-Null
    if ($ConfigOnly) { $status = "passed"; return }
    if (-not $Start) { throw "Use -Start for stateful acceptance or -ConfigOnly for interpolation only." }
    Assert-OperatorInput

    Invoke-Compose "Start stateful foundations" @("up", "-d", "connector-postgres", "keycloak", "openbao") | Out-Null
    $started = $true
    $initOutput = Invoke-Compose "Initialize OpenBao" @("exec", "-T", "openbao", "bao", "operator", "init", "-key-shares=3", "-key-threshold=2", "-format=json") -Sensitive
    $init = ($initOutput -join "`n") | ConvertFrom-Json
    $unsealKeys = @($init.unseal_keys_b64)
    if ($unsealKeys.Count -ne 3 -or [string]::IsNullOrWhiteSpace($init.root_token)) { throw "OpenBao initialization returned an invalid finite result." }
    for ($index = 0; $index -lt 3; $index++) { Set-Content -LiteralPath (Join-Path $recoveryRoot "share-$($index + 1)") -Value $unsealKeys[$index] -NoNewline }
    Set-Content -LiteralPath (Join-Path $operatorRoot "root-token") -Value $init.root_token -NoNewline
    Invoke-Compose "Manual unseal share 1" @("exec", "-T", "openbao", "bao", "operator", "unseal", $unsealKeys[0]) -Sensitive | Out-Null
    Invoke-Compose "Manual unseal share 2" @("exec", "-T", "openbao", "bao", "operator", "unseal", $unsealKeys[1]) -Sensitive | Out-Null

    $policy = Get-Content -LiteralPath (Join-Path $root "infra/openbao/policies/projecta-api.hcl") -Raw
    $policy | & docker compose -p $project -f (Join-Path $root "compose.yaml") -f (Join-Path $root "compose.prod.yaml") exec -T -e "BAO_TOKEN=$($init.root_token)" openbao bao policy write projecta-api - | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "OpenBao policy bootstrap failed." }
    Invoke-Compose "Enable AppRole" @("exec", "-T", "-e", "BAO_TOKEN=$($init.root_token)", "openbao", "bao", "auth", "enable", "approle") | Out-Null
    Invoke-Compose "Configure bounded workload role" @("exec", "-T", "-e", "BAO_TOKEN=$($init.root_token)", "openbao", "bao", "write", "auth/approle/role/projecta-api", "token_policies=projecta-api", "token_ttl=15m", "token_max_ttl=60m", "secret_id_ttl=10m", "secret_id_num_uses=1") | Out-Null
    $roleId = (Invoke-Compose "Issue workload RoleID" @("exec", "-T", "-e", "BAO_TOKEN=$($init.root_token)", "openbao", "bao", "read", "-field=role_id", "auth/approle/role/projecta-api/role-id") -Sensitive | Select-Object -Last 1).Trim()
    $secretId = (Invoke-Compose "Issue single-use workload SecretID" @("exec", "-T", "-e", "BAO_TOKEN=$($init.root_token)", "openbao", "bao", "write", "-field=secret_id", "-f", "auth/approle/role/projecta-api/secret-id") -Sensitive | Select-Object -Last 1).Trim()
    Set-Content -LiteralPath $roleIdFile -Value $roleId -NoNewline
    Set-Content -LiteralPath $secretIdFile -Value $secretId -NoNewline

    # Production OIDC discovery is intentionally routed through the edge alias
    # (auth.example.com). Start that proxy in the same batch as the API so the
    # nginx resolves its web upstream during startup. Create that upstream
    # before edge, but let the API/edge pair be the readiness-gated batch.
    Invoke-Compose "Create web upstream before edge" @("up", "-d", "web") | Out-Null
    # Production OIDC discovery is routed through the edge alias
    # (auth.example.com), so edge must exist while Compose waits for API health.
    Invoke-Compose "Start API and edge after foundations" @("up", "-d", "--wait", "semantic-core", "api", "edge") | Out-Null
    Invoke-Compose "Start complete production topology" @("up", "-d", "--wait") | Out-Null
    Invoke-Compose "Production readiness probe" @("exec", "-T", "api", "python", "-c", "from urllib.request import urlopen; assert urlopen('http://127.0.0.1:8000/health/ready').status == 200") | Out-Null
    Invoke-Compose "Deterministic identity, secret, Teams, and GitHub journeys" @("run", "--build", "--rm", "--no-deps", "connector-operational-test", "uv", "run", "pytest", "-q", "tests/test_sprint11_identity.py", "tests/test_sprint11_openbao.py", "tests/test_sprint11_teams_setup.py", "tests/test_sprint11_teams_adapter.py", "tests/test_sprint11_github_mapping.py", "tests/test_sprint11_github_setup.py", "tests/test_sprint11_github_transport.py") | Out-Null
    Invoke-Compose "Stop application before operator re-authentication" @("stop", "api") | Out-Null
    $replacementSecretId = (Invoke-Compose "Issue replacement SecretID after workload stop" @("exec", "-T", "-e", "BAO_TOKEN=$($init.root_token)", "openbao", "bao", "write", "-field=secret_id", "-f", "auth/approle/role/projecta-api/secret-id") -Sensitive | Select-Object -Last 1).Trim()
    Set-Content -LiteralPath $secretIdFile -Value $replacementSecretId -NoNewline
    Invoke-Compose "Readiness after restart and AppRole re-authentication" @("up", "-d", "--force-recreate", "--wait", "api") | Out-Null
    Invoke-Compose "Revoke bootstrap root token" @("exec", "-T", "-e", "BAO_TOKEN=$($init.root_token)", "openbao", "bao", "token", "revoke", "-self") -Sensitive | Out-Null
    Invoke-Compose "Collect final service state" @("ps", "--format", "json") | Out-Null
    $logs = Invoke-Compose "Collect bounded runtime logs" @("logs", "--no-color", "--tail", "300")
    if (($logs -join "`n") -match '(?i)(-----BEGIN (RSA |EC |)PRIVATE KEY-----|client_secret|secret_id\s*[=:]\s*[^*\s])') { throw "Runtime log leak signature detected." }
    $status = "passed"
} catch {
    $failure = $_.Exception.Message
    if ($started) {
        $diagnosticStarted = [DateTime]::UtcNow
        $diagnostic = @(& docker compose -p $project -f (Join-Path $root "compose.yaml") -f (Join-Path $root "compose.prod.yaml") logs --no-color --tail 80 api 2>&1 | ForEach-Object {
            ([string]$_) -replace '(?i)(token|secret|password|private[_-]?key)\s*[=:]\s*[^\s,;]+', '$1=<redacted>'
        })
        $readyDiagnostic = @(& docker compose -p $project -f (Join-Path $root "compose.yaml") -f (Join-Path $root "compose.prod.yaml") exec -T api python -c "import httpx; response = httpx.get('http://127.0.0.1:8000/health/ready'); print(response.status_code); print(response.text)" 2>&1 | ForEach-Object {
            ([string]$_) -replace '(?i)(token|secret|password|private[_-]?key)\s*[=:]\s*[^\s,;]+', '$1=<redacted>'
        })
        $diagnostic += "readinessBody=" + ($readyDiagnostic -join " ")
        $results.Add([pscustomobject]@{
            name = "Failure diagnostics: API logs"
            exitCode = 0
            startedAt = $diagnosticStarted.ToString("o")
            finishedAt = [DateTime]::UtcNow.ToString("o")
            output = @($diagnostic | Select-Object -Last 80)
        })
    }
    Write-Error $failure
} finally {
    if ($started) { docker compose -p $project -f (Join-Path $root "compose.yaml") -f (Join-Path $root "compose.prod.yaml") down --volumes --remove-orphans | Out-Host }
    if (Test-Path -LiteralPath $operatorRoot) { Remove-Item -LiteralPath $operatorRoot -Recurse -Force }
    New-Item -ItemType Directory -Path (Split-Path -Parent $evidence) -Force | Out-Null
    [pscustomobject]@{ schemaVersion = "sprint11.clean-compose.v2"; status = $status; project = $project; startedAt = $startedAt.ToString("o"); finishedAt = [DateTime]::UtcNow.ToString("o"); failure = $failure; gates = @($results) } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $evidence -Encoding utf8
}
if ($status -ne "passed") { exit 1 }
