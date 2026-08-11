param(
    [switch]$AllowDirtyWorktree,
    [string]$EvidencePath = "docs/sprint-plans/sprint-10/artifacts/s10-61-validation.json"
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$apiRoot = (Resolve-Path (Join-Path $root "apps/api")).Path
$webRoot = (Resolve-Path (Join-Path $root "apps/web")).Path
$evidenceFile = Join-Path $root $EvidencePath
$composeProject = "projecta-s10-validation-$([guid]::NewGuid().ToString('N').Substring(0, 12))"
$results = [System.Collections.Generic.List[object]]::new()
$startedAt = [DateTime]::UtcNow
$composeStarted = $false
$savedEnvironment = @{}
$composeEnvironment = @{
    PROJECTA_API_TRUSTED_CONTEXT_SECRET = "s10-validation-trusted-context"
    PROJECTA_CONNECTOR_POSTGRES_USER = "connector_validation"
    PROJECTA_CONNECTOR_POSTGRES_PASSWORD = "s10-validation-password"
    PROJECTA_CONNECTOR_POSTGRES_DB = "projecta_validation"
    CONNECTOR_POSTGRES_IMAGE = "postgres:16.4-alpine"
    API_IMAGE = "projecta-api:validation"
    WEB_IMAGE = "projecta-web:validation"
    SEMANTIC_CORE_IMAGE = "projecta-semantic-core:validation"
}

function Save-Environment {
    $masterKeyPath = "Env:PROJECTA_API_SECRET_STORE_MASTER_KEY"
    $savedEnvironment["PROJECTA_API_SECRET_STORE_MASTER_KEY"] = @{
        Exists = Test-Path $masterKeyPath
        Value = if (Test-Path $masterKeyPath) { (Get-Item $masterKeyPath).Value } else { $null }
    }
    foreach ($entry in $composeEnvironment.GetEnumerator()) {
        $path = "Env:$($entry.Key)"
        $savedEnvironment[$entry.Key] = @{
            Exists = Test-Path $path
            Value = if (Test-Path $path) { (Get-Item $path).Value } else { $null }
        }
    }
}

function Set-ComposeEnvironment {
    foreach ($entry in $composeEnvironment.GetEnumerator()) {
        Set-Item -Path "Env:$($entry.Key)" -Value $entry.Value
    }
}

function Restore-Environment {
    foreach ($entry in $savedEnvironment.GetEnumerator()) {
        $path = "Env:$($entry.Key)"
        if ($entry.Value.Exists) {
            Set-Item -Path $path -Value $entry.Value.Value
        } else {
            Remove-Item -Path $path -ErrorAction SilentlyContinue
        }
    }
}

function Invoke-Gate {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$Arguments = @(),
        [string]$WorkingDirectory = $root
    )
    $commandText = "$FilePath $($Arguments -join ' ')"
    Write-Host "[S10-61] $Name"
    $gateStart = [DateTime]::UtcNow
    Push-Location $WorkingDirectory
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        # Some valid tools (notably Python unittest) write progress to stderr.
        # Capture that stream as evidence and decide pass/fail from the native exit code.
        $ErrorActionPreference = "Continue"
        $output = @(& $FilePath @Arguments 2>&1 | ForEach-Object { [string]$_ })
        $exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { [int]$LASTEXITCODE }
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
        Pop-Location
    }
    $record = [pscustomobject]@{
        name = $Name
        command = $commandText
        startedAt = $gateStart.ToString("o")
        finishedAt = [DateTime]::UtcNow.ToString("o")
        exitCode = $exitCode
        output = ($output | Select-Object -Last 200)
    }
    $results.Add($record)
    $output | Select-Object -Last 20 | ForEach-Object { Write-Host $_ }
    if ($exitCode -ne 0) {
        throw "$Name failed with exit code $exitCode."
    }
}

function Write-Evidence([string]$Status, [string]$Failure = $null) {
    $parent = Split-Path -Parent $evidenceFile
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    [pscustomobject]@{
        schemaVersion = "s10.validation.v1"
        status = $Status
        startedAt = $startedAt.ToString("o")
        finishedAt = [DateTime]::UtcNow.ToString("o")
        worktreeWasClean = $worktreeWasClean
        allowDirtyWorktree = [bool]$AllowDirtyWorktree
        composeProject = $composeProject
        failure = $Failure
        gates = @($results)
    } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $evidenceFile -Encoding utf8
}

$worktreeWasClean = $false
try {
    Push-Location $root
    try {
        $statusLines = @(git status --porcelain)
        $worktreeWasClean = $statusLines.Count -eq 0
        if (-not $worktreeWasClean -and -not $AllowDirtyWorktree) {
            throw "S10-61 requires a clean checkout. Re-run only on the reviewed checkout or explicitly use -AllowDirtyWorktree for diagnostic evidence."
        }

        Save-Environment
        Invoke-Gate "Release-contract unit tests" "python" @("-m", "unittest", "discover", "-s", "scripts/tests", "-p", "test_*.py")
        Invoke-Gate "API Ruff" "uv" @("run", "ruff", "check", ".") $apiRoot
        Invoke-Gate "API Pyright" "uv" @("run", "pyright") $apiRoot
        Invoke-Gate "API full tests" "uv" @("run", "pytest", "-q") $apiRoot
        Invoke-Gate "Web dependency install" "npm" @("ci", "--ignore-scripts") $webRoot
        Invoke-Gate "Web dependency audit" "npm" @("audit", "--audit-level=high") $webRoot
        Invoke-Gate "Web format" "npm" @("run", "format:check") $webRoot
        Invoke-Gate "Web typecheck" "npm" @("run", "typecheck") $webRoot
        Invoke-Gate "Web lint" "npm" @("run", "lint") $webRoot
        Invoke-Gate "Web unit tests" "npm" @("test", "--", "--run") $webRoot
        Invoke-Gate "Web Nginx contract" "npm" @("run", "check:nginx-config") $webRoot
        Invoke-Gate "Web API drift" "npm" @("run", "check:api-drift") $webRoot
        Invoke-Gate "Web production build" "npm" @("run", "build") $webRoot
        $savedNoColor = if (Test-Path Env:NO_COLOR) { (Get-Item Env:NO_COLOR).Value } else { $null }
        try {
            Remove-Item Env:NO_COLOR -ErrorAction SilentlyContinue
            Invoke-Gate "Deterministic browser tests" "npx" @("playwright", "test", "--workers=1") $webRoot
        } finally {
            if ($null -ne $savedNoColor) { Set-Item Env:NO_COLOR $savedNoColor }
        }
        Invoke-Gate "Semantic Core verification" "mvn" @("--batch-mode", "verify") (Join-Path $root "services/semantic-core")
        Invoke-Gate "UI contract" "node" @((Join-Path $root ".agents/skills/build-databricks-ui/scripts/check-ui-contract.mjs"), (Join-Path $webRoot "src/styles.css"))
        Invoke-Gate "Implicit behavior contract" "pwsh" @("-NoProfile", "-File", (Join-Path $root "scripts/check_sprint8_implicit_behaviors.ps1"))
        Invoke-Gate "Compose health contract" "pwsh" @("-NoProfile", "-File", (Join-Path $root "scripts/check_sprint8_health_contract.ps1"))
        Invoke-Gate "Sprint 10 repository contract" "python" @("scripts/check_sprint10_repository_contract.py")
        $leakMarker = "s10-validation-$([guid]::NewGuid().ToString('N'))"
        Invoke-Gate "Secret leak gate" "pwsh" @("-NoProfile", "-File", (Join-Path $root "scripts/check_secret_leaks.ps1"), "-Secret", $leakMarker)
        Set-ComposeEnvironment
        $masterKeyBytes = New-Object byte[] 32
        $random = [System.Security.Cryptography.RandomNumberGenerator]::Create()
        try { $random.GetBytes($masterKeyBytes) }
        finally { $random.Dispose() }
        Set-Item Env:PROJECTA_API_SECRET_STORE_MASTER_KEY ([Convert]::ToBase64String($masterKeyBytes).Replace('+', '-').Replace('/', '_'))
        Invoke-Gate "Compose interpolation" "docker" @("compose", "-p", $composeProject, "--profile", "web", "config", "--quiet")
        Invoke-Gate "Ontology validation" "docker" @("compose", "-p", $composeProject, "--profile", "tools", "run", "--build", "--rm", "ontology-test")
        $composeStarted = $true
        Invoke-Gate "Connector migration and integration" "docker" @("compose", "-p", $composeProject, "--profile", "system-test", "run", "--build", "--rm", "connector-operational-test")
        Invoke-Gate "Whitespace contract" "git" @("diff", "--check")
        Write-Evidence "passed"
        Write-Host "Sprint 10 validation passed. Evidence: $evidenceFile"
        exit 0
    } finally {
        Pop-Location
    }
} catch {
    $failure = $_.Exception.Message
    try { Write-Evidence "failed" $failure } catch { Write-Error "Could not write validation evidence: $($_.Exception.Message)" }
    Write-Error $failure
    exit 1
} finally {
    if ($composeStarted) {
        docker compose -p $composeProject --profile system-test --profile tools --profile web down --volumes --remove-orphans | Out-Host
    }
    Restore-Environment
}
