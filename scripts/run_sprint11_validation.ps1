param(
    [switch]$AllowDirtyWorktree,
    [switch]$SkipComposeConfig,
    [string]$EvidencePath = "docs/sprint-plans/sprint-11/artifacts/s11-65-validation.json"
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$apiRoot = (Resolve-Path (Join-Path $root "apps/api")).Path
$webRoot = (Resolve-Path (Join-Path $root "apps/web")).Path
$evidence = Join-Path $root $EvidencePath
$results = [System.Collections.Generic.List[object]]::new()
$startedAt = [DateTime]::UtcNow

function Invoke-Gate {
    param([string]$Name, [string]$FilePath, [string[]]$Arguments = @(), [string]$WorkingDirectory = $root)
    $gateStart = [DateTime]::UtcNow
    Push-Location $WorkingDirectory
    try {
        $output = @(& $FilePath @Arguments 2>&1 | ForEach-Object { [string]$_ })
        $exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { [int]$LASTEXITCODE }
    } finally { Pop-Location }
    $results.Add([pscustomobject]@{ name = $Name; command = "$FilePath $($Arguments -join ' ')"; exitCode = $exitCode; output = ($output | Select-Object -Last 120); startedAt = $gateStart.ToString("o"); finishedAt = [DateTime]::UtcNow.ToString("o") })
    $output | Select-Object -Last 12 | ForEach-Object { Write-Host $_ }
    if ($exitCode -ne 0) { throw "$Name failed with exit code $exitCode." }
}

$status = "failed"
$failure = $null
try {
    $dirty = @(git -C $root status --porcelain)
    if ($dirty.Count -gt 0 -and -not $AllowDirtyWorktree) { throw "S11-65 requires a reviewed clean worktree; use -AllowDirtyWorktree for diagnostic evidence." }
    Invoke-Gate "Sprint 11 repository contract" "python" @((Join-Path $root "scripts/check_sprint11_repository_contract.py"))
    Invoke-Gate "GitHub Public Issues evidence contract" "python" @((Join-Path $root "scripts/check_sprint11_github_live_evidence.py"))
    Invoke-Gate "Sprint 11 contract matrix" "uv" @("run", "--project", "apps/api", "pytest", "-c", "apps/api/pyproject.toml", "-p", "no:cacheprovider", "-q", "scripts/tests/test_sprint11_phase_a_contract.py", "scripts/tests/test_sprint11_identity_contract.py", "scripts/tests/test_sprint11_openbao_contract.py", "scripts/tests/test_sprint11_teams_contract.py", "scripts/tests/test_sprint11_secret_leak_contract.py", "scripts/tests/test_sprint11_phase_e_contract.py", "scripts/tests/test_sprint11_phase_f_contract.py")
    Invoke-Gate "GitHub Public Issues deterministic tests" "uv" @("run", "pytest", "-q", "tests/test_sprint11_github_mapping.py", "tests/test_sprint11_github_setup.py", "tests/test_sprint11_github_transport.py") $apiRoot
    Invoke-Gate "API Ruff" "uv" @("run", "ruff", "check", ".") $apiRoot
    Invoke-Gate "API strict Pyright" "uv" @("run", "pyright") $apiRoot
    Invoke-Gate "API full tests" "uv" @("run", "pytest", "-q") $apiRoot
    Invoke-Gate "Web format" "npm" @("run", "format:check") $webRoot
    Invoke-Gate "Web typecheck" "npm" @("run", "typecheck") $webRoot
    Invoke-Gate "Web lint" "npm" @("run", "lint") $webRoot
    Invoke-Gate "Web unit tests" "npm" @("test", "--", "--run") $webRoot
    Invoke-Gate "Web Nginx contract" "npm" @("run", "check:nginx-config") $webRoot
    Invoke-Gate "Web API drift" "npm" @("run", "check:api-drift") $webRoot
    Invoke-Gate "Web production build" "npm" @("run", "build") $webRoot
    Invoke-Gate "Semantic Core verification" "mvn" @("--batch-mode", "verify") (Join-Path $root "services/semantic-core")
    $leakMarker = "s11-validation-$([guid]::NewGuid().ToString('N'))"
    Invoke-Gate "Secret leak gate" "pwsh" @("-NoProfile", "-File", (Join-Path $root "scripts/check_secret_leaks.ps1"), "-Secret", $leakMarker)
    if (-not $SkipComposeConfig) {
        $env:CONNECTOR_POSTGRES_IMAGE = "postgres:16.4-alpine@sha256:validation"
        $env:KEYCLOAK_IMAGE = "quay.io/keycloak/keycloak:26.7.0@sha256:validation"
        $env:OPENBAO_IMAGE = "ghcr.io/openbao/openbao:2.6.1@sha256:validation"
        $env:EDGE_IMAGE = "nginx:1.29-alpine@sha256:validation"
        $env:API_IMAGE = "projecta-api:validation@sha256:validation"
        $env:WEB_IMAGE = "projecta-web:validation@sha256:validation"
        $env:SEMANTIC_CORE_IMAGE = "projecta-semantic-core:validation@sha256:validation"
        $env:PROJECTA_CONNECTOR_POSTGRES_USER = "validation"
        $env:PROJECTA_CONNECTOR_POSTGRES_PASSWORD = "validation-only"
        $env:PROJECTA_CONNECTOR_POSTGRES_DB = "projecta"
        $env:PROJECTA_KEYCLOAK_POSTGRES_DB = "keycloak"
        $env:PROJECTA_KEYCLOAK_POSTGRES_USER = "keycloak"
        $env:PROJECTA_KEYCLOAK_POSTGRES_PASSWORD = "validation-only"
        $env:KEYCLOAK_BOOTSTRAP_ADMIN_USERNAME = "operator"
        $env:KEYCLOAK_BOOTSTRAP_ADMIN_PASSWORD = "validation-only"
        $env:PROJECTA_API_TRUSTED_CONTEXT_SECRET = "s11-validation-trusted-context"
        $env:PROJECTA_API_SECRET_STORE_MASTER_KEY = "s11-validation-compose-only"
        $env:PROJECTA_OPENBAO_ROLE_ID_FILE = (Join-Path $root "infra/env/role-id.validation")
        $env:PROJECTA_OPENBAO_SECRET_ID_FILE = (Join-Path $root "infra/env/secret-id.validation")
        Invoke-Gate "Production Compose interpolation" "docker" @("compose", "-f", "compose.yaml", "-f", "compose.prod.yaml", "config", "--quiet")
        $composeProject = "projecta-s11-validation-$([guid]::NewGuid().ToString('N').Substring(0, 12))"
        try {
            Invoke-Gate "Ontology validation" "docker" @("compose", "-p", $composeProject, "--profile", "tools", "run", "--build", "--rm", "ontology-test")
            Invoke-Gate "Connector migration and integration" "docker" @("compose", "-p", $composeProject, "--profile", "system-test", "run", "--build", "--rm", "connector-operational-test")
        } finally {
            docker compose -p $composeProject --profile tools --profile system-test down --volumes --remove-orphans | Out-Host
        }
    }
    Invoke-Gate "Whitespace" "git" @("-C", $root, "diff", "--check")
    $status = "passed"
} catch { $failure = $_.Exception.Message; Write-Error $failure }
finally {
    $parent = Split-Path -Parent $evidence
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    [pscustomobject]@{ schemaVersion = "sprint11.validation.v1"; status = $status; startedAt = $startedAt.ToString("o"); finishedAt = [DateTime]::UtcNow.ToString("o"); failure = $failure; gates = @($results) } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $evidence -Encoding utf8
}
if ($status -ne "passed") { exit 1 }
