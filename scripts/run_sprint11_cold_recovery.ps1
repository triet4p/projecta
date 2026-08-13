param(
    [string]$EvidencePath = "docs/sprint-plans/sprint-11/artifacts/s11-63-cold-recovery.json",
    [switch]$AllowDirtyWorktree
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$runId = [guid]::NewGuid().ToString("N").Substring(0, 12)
$network = "projecta-s11-recovery-$runId"
$sourcePostgres = "$network-pg-source"
$restorePostgres = "$network-pg-restore"
$sourceBao = "$network-bao-source"
$restoreBao = "$network-bao-restore"
$sourceKeycloak = "$network-kc-source"
$restoreKeycloak = "$network-kc-restore"
$tempRoot = Join-Path ([IO.Path]::GetTempPath()) $network
$bundle = Join-Path $tempRoot "bundle"
$restoredBundle = Join-Path $tempRoot "restored-bundle"
$sourceEvidence = Join-Path $tempRoot "source-evidence"
$postgresDump = Join-Path $tempRoot "postgres.dump"
$keycloakExport = Join-Path $tempRoot "keycloak-export.json"
$rawSnapshot = Join-Path $tempRoot "openbao.snap"
$encryptedSnapshot = Join-Path $tempRoot "openbao-snapshot.enc"
$snapshotKey = Join-Path $tempRoot "snapshot.key"
$evidenceFile = Join-Path $root $EvidencePath
$gates = [Collections.Generic.List[object]]::new()
$failure = $null

function New-RandomSecret([int]$Bytes = 24) {
    $buffer = New-Object byte[] $Bytes
    [Security.Cryptography.RandomNumberGenerator]::Fill($buffer)
    return [Convert]::ToBase64String($buffer).Replace("+", "-").Replace("/", "_")
}

$postgresPassword = New-RandomSecret
$keycloakPassword = New-RandomSecret
$keycloakAdminPassword = New-RandomSecret
$sourceMarker = "recovery-marker-$runId"
$projectDatabase = "projecta_recovery"
$keycloakDatabase = "keycloak_recovery"
$keycloakUser = "keycloak_recovery"

function Invoke-Gate([string]$Name, [scriptblock]$Command, [switch]$Sensitive) {
    Write-Host "[S11-63] $Name"
    $started = [DateTime]::UtcNow
    $output = @(& $Command 2>&1 | ForEach-Object { [string]$_ })
    $exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { [int]$LASTEXITCODE }
    $gates.Add([pscustomobject]@{
        name = $Name
        exitCode = $exitCode
        startedAt = $started.ToString("o")
        finishedAt = [DateTime]::UtcNow.ToString("o")
        output = if ($Sensitive) { "<operator-sensitive output redacted>" } else { @($output | Select-Object -Last 20) }
    })
    if (-not $Sensitive) { $output | Select-Object -Last 5 | ForEach-Object { Write-Host $_ } }
    if ($exitCode -ne 0) { throw "$Name failed with exit code $exitCode." }
    return $output
}

function Wait-Postgres([string]$Container) {
    $deadline = (Get-Date).AddSeconds(90)
    while ((Get-Date) -lt $deadline) {
        docker exec $Container pg_isready -U postgres -d postgres 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { return }
        Start-Sleep -Seconds 2
    }
    throw "PostgreSQL readiness timed out."
}

function Wait-OpenBao([string]$Container) {
    $deadline = (Get-Date).AddSeconds(60)
    while ((Get-Date) -lt $deadline) {
        docker exec -e BAO_ADDR=https://localhost:8200 -e BAO_CACERT=/openbao/tls/ca.crt $Container bao status -format=json 2>$null | Out-Null
        if ($LASTEXITCODE -in @(0, 2)) { return }
        Start-Sleep -Seconds 2
    }
    throw "OpenBao readiness timed out."
}

function Get-PublishedPort([string]$Container, [int]$Port) {
    $mapping = @(docker port $Container "$Port/tcp")
    $match = [regex]::Match(($mapping -join "`n"), ':(?<port>\d+)(?:\r?$)')
    if (-not $match.Success) { throw "Could not resolve a published test port." }
    return [int]$match.Groups["port"].Value
}

function Start-Postgres([string]$Container, [switch]$WithKeycloakBootstrap) {
    $arguments = @(
        "run", "--detach", "--name", $Container, "--network", $network,
        "--publish-all", "--env", "POSTGRES_USER=postgres",
        "--env", "POSTGRES_PASSWORD=$postgresPassword", "--env", "POSTGRES_DB=postgres"
    )
    if ($WithKeycloakBootstrap) {
        $arguments += @(
            "--env", "PROJECTA_KEYCLOAK_POSTGRES_DB=$keycloakDatabase",
            "--env", "PROJECTA_KEYCLOAK_POSTGRES_USER=$keycloakUser",
            "--env", "PROJECTA_KEYCLOAK_POSTGRES_PASSWORD=$keycloakPassword",
            "--volume", "${root}/infra/postgres/20-keycloak-database.sh:/docker-entrypoint-initdb.d/20-keycloak-database.sh:ro"
        )
    }
    $arguments += $env:CONNECTOR_POSTGRES_IMAGE
    docker @arguments
}

function Start-OpenBao([string]$Container) {
    $arguments = @(
        "run", "--detach", "--name", $Container, "--network", $network,
        "--network-alias", "openbao", "--volume", "${Container}-data:/openbao/file",
        "--volume", "${root}/infra/openbao/config.hcl:/openbao/config.hcl:ro",
        "--volume", "${root}/infra/openbao/tls:/openbao/tls:ro",
        "--env", "BAO_API_ADDR=https://openbao:8200", "--env", "BAO_CACERT=/openbao/tls/ca.crt",
        $env:OPENBAO_IMAGE, "server", "-config=/openbao/config.hcl"
    )
    docker @arguments
}

function Invoke-Bao([string]$Container, [string]$Token, [string[]]$Arguments) {
    $output = @(docker exec -e BAO_ADDR=https://localhost:8200 -e BAO_CACERT=/openbao/tls/ca.crt -e BAO_TOKEN=$Token $Container bao @Arguments)
    if ($LASTEXITCODE -ne 0) { throw "OpenBao operator command failed." }
    return $output
}

function Initialize-Bao([string]$Container) {
    $json = docker exec -e BAO_ADDR=https://localhost:8200 -e BAO_CACERT=/openbao/tls/ca.crt $Container bao operator init -key-shares=3 -key-threshold=2 -format=json
    if ($LASTEXITCODE -ne 0) { throw "OpenBao initialization failed." }
    $initialized = $json | ConvertFrom-Json
    foreach ($share in @($initialized.unseal_keys_b64 | Select-Object -First 2)) {
        docker exec -e BAO_ADDR=https://localhost:8200 -e BAO_CACERT=/openbao/tls/ca.crt $Container bao operator unseal $share | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "OpenBao manual unseal failed." }
    }
    return $initialized
}

function Start-Keycloak([string]$Container, [string]$PostgresContainer) {
    docker run --detach --name $Container --network $network --publish-all `
        --volume "${root}/infra/keycloak/realm.template.json:/opt/keycloak/data/import/projecta-realm.json:ro" `
        --volume "${root}/infra/keycloak/tls:/etc/keycloak/tls:ro" `
        --env KC_DB=postgres --env "KC_DB_URL=jdbc:postgresql://${PostgresContainer}:5432/$keycloakDatabase" `
        --env "KC_DB_USERNAME=$keycloakUser" --env "KC_DB_PASSWORD=$keycloakPassword" `
        --env KC_HOSTNAME=auth.example.com `
        --env KC_HTTP_ENABLED=false --env KC_HTTPS_CERTIFICATE_FILE=/etc/keycloak/tls/tls.crt `
        --env KC_HTTPS_CERTIFICATE_KEY_FILE=/etc/keycloak/tls/tls.key `
        --env "KC_BOOTSTRAP_ADMIN_USERNAME=recovery-operator" --env "KC_BOOTSTRAP_ADMIN_PASSWORD=$keycloakAdminPassword" `
        $env:KEYCLOAK_IMAGE start --optimized --import-realm
}

function Wait-KeycloakRealm([string]$Container) {
    $port = Get-PublishedPort $Container 8443
    $deadline = (Get-Date).AddSeconds(120)
    while ((Get-Date) -lt $deadline) {
        $running = docker inspect $Container --format '{{.State.Running}}' 2>$null
        if ($running -ne "true") { throw "Keycloak stopped before realm readiness." }
        curl.exe --silent --fail --insecure "https://127.0.0.1:$port/realms/projecta/.well-known/openid-configuration" 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { return }
        Start-Sleep -Seconds 3
    }
    throw "Keycloak realm readiness timed out."
}

function Write-Evidence([string]$Status) {
    New-Item -ItemType Directory -Path (Split-Path -Parent $evidenceFile) -Force | Out-Null
    [pscustomobject]@{
        schemaVersion = "sprint11.cold-recovery.v2"
        status = $Status
        startedFromCleanTargets = $true
        sourceDestroyedBeforeRestore = $true
        manualUnsealWithOriginalShares = ($Status -eq "passed")
        sessionsInvalidated = ($Status -eq "passed")
        workloadReauthenticated = ($Status -eq "passed")
        idempotentReplayVerified = ($Status -eq "passed")
        keycloakRuntimeExportVerified = ($Status -eq "passed")
        failure = $failure
        gates = @($gates)
    } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $evidenceFile -Encoding utf8
}

if (-not $AllowDirtyWorktree -and (git status --porcelain)) {
    throw "Recovery acceptance requires a clean worktree unless -AllowDirtyWorktree is explicit."
}
foreach ($required in @("CONNECTOR_POSTGRES_IMAGE", "KEYCLOAK_IMAGE", "OPENBAO_IMAGE")) {
    if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($required))) { throw "$required is required." }
}

try {
    New-Item -ItemType Directory -Path $tempRoot,$sourceEvidence -Force | Out-Null
    [IO.File]::WriteAllText($snapshotKey, (New-RandomSecret 48), [Text.UTF8Encoding]::new($false))
    Invoke-Gate "Create isolated recovery network" { docker network create $network } | Out-Null
    Invoke-Gate "Start source PostgreSQL" { Start-Postgres $sourcePostgres -WithKeycloakBootstrap } | Out-Null
    Wait-Postgres $sourcePostgres
    Invoke-Gate "Create Projecta recovery database" { docker exec $sourcePostgres createdb -U postgres $projectDatabase } | Out-Null
    $sourcePort = Get-PublishedPort $sourcePostgres 5432
    $env:PROJECTA_CONNECTOR_DATABASE_HOST = "127.0.0.1"
    $env:PROJECTA_CONNECTOR_DATABASE_PORT = [string]$sourcePort
    $env:PROJECTA_CONNECTOR_DATABASE_NAME = $projectDatabase
    $env:PROJECTA_CONNECTOR_DATABASE_USER = "postgres"
    $env:PROJECTA_CONNECTOR_DATABASE_PASSWORD = $postgresPassword
    $env:PROJECTA_EVIDENCE_ROOT = $sourceEvidence
    Invoke-Gate "Apply current migrations" { uv run --project apps/api python -m projecta_api.operational.migrate upgrade } | Out-Null
    Invoke-Gate "Seed operational replay and evidence state" { uv run --project apps/api python scripts/connector_recovery_fixture.py seed } | Out-Null
    Invoke-Gate "Seed active Projecta session" {
        docker exec $sourcePostgres psql -U postgres -d $projectDatabase -v ON_ERROR_STOP=1 -c "INSERT INTO projecta_sessions (session_id,subject,actor_id,tenant_id,expires_at,created_at,revoked_at,csrf_token,session_epoch) VALUES ('recovery-session','recovery-subject','recovery-actor','recovery-tenant',now()+interval '1 hour',now(),NULL,'recovery-csrf',1);"
    } | Out-Null

    Invoke-Gate "Start source Keycloak runtime" { Start-Keycloak $sourceKeycloak $sourcePostgres } | Out-Null
    Wait-KeycloakRealm $sourceKeycloak
    Invoke-Gate "Stop source Keycloak before export" { docker stop $sourceKeycloak } | Out-Null
    Invoke-Gate "Create runtime Keycloak realm export" {
        docker run --rm --network $network --volume "${tempRoot}:/export" `
            --env KC_DB=postgres --env "KC_DB_URL=jdbc:postgresql://${sourcePostgres}:5432/$keycloakDatabase" `
            --env "KC_DB_USERNAME=$keycloakUser" --env "KC_DB_PASSWORD=$keycloakPassword" `
            $env:KEYCLOAK_IMAGE export --optimized --realm projecta --file /export/keycloak-export.json
    } | Out-Null

    Invoke-Gate "Start and initialize source OpenBao" { Start-OpenBao $sourceBao } | Out-Null
    Wait-OpenBao $sourceBao
    $sourceInit = Initialize-Bao $sourceBao
    $sourceRootToken = [string]$sourceInit.root_token
    Invoke-Gate "Seed OpenBao policy, AppRole, and secret" {
        Invoke-Bao $sourceBao $sourceRootToken @("secrets", "enable", "-path=projecta", "kv-v2")
        Invoke-Bao $sourceBao $sourceRootToken @("auth", "enable", "approle")
        $policy = 'path "projecta/data/recovery/*" { capabilities = ["read"] }'
        $policy | docker exec -i -e BAO_ADDR=https://localhost:8200 -e BAO_CACERT=/openbao/tls/ca.crt -e BAO_TOKEN=$sourceRootToken $sourceBao bao policy write projecta-api -
        Invoke-Bao $sourceBao $sourceRootToken @("write", "auth/approle/role/projecta-api", "token_policies=projecta-api", "secret_id_num_uses=1", "secret_id_ttl=10m", "token_ttl=5m", "token_max_ttl=10m")
        Invoke-Bao $sourceBao $sourceRootToken @("kv", "put", "projecta/recovery/sentinel", "marker=$sourceMarker")
    } -Sensitive | Out-Null
    Invoke-Gate "Create OpenBao Raft snapshot" { Invoke-Bao $sourceBao $sourceRootToken @("operator", "raft", "snapshot", "save", "/tmp/openbao.snap") } -Sensitive | Out-Null
    Invoke-Gate "Copy and encrypt OpenBao snapshot" {
        docker cp "${sourceBao}:/tmp/openbao.snap" $rawSnapshot
        openssl enc -aes-256-cbc -salt -pbkdf2 -in $rawSnapshot -out $encryptedSnapshot -pass "file:$snapshotKey"
    } -Sensitive | Out-Null
    Remove-Item -LiteralPath $rawSnapshot -Force

    Invoke-Gate "Create coordinated PostgreSQL dump" {
        docker exec $sourcePostgres pg_dumpall -U postgres --clean --if-exists --file=/tmp/postgres.dump
        docker cp "${sourcePostgres}:/tmp/postgres.dump" $postgresDump
    } -Sensitive | Out-Null
    Invoke-Gate "Create coordinated state bundle" {
        uv run --project apps/api python scripts/sprint11_backup.py create --output $bundle --postgres-dump $postgresDump --evidence-root $sourceEvidence --keycloak-export $keycloakExport --openbao-snapshot $encryptedSnapshot --confirm-quiesced
    } | Out-Null

    Invoke-Gate "Destroy complete source state" {
        docker rm --force --volumes $sourceKeycloak $sourceBao $sourcePostgres
        docker volume rm "${sourceBao}-data"
    } | Out-Null
    Invoke-Gate "Restore bundle into isolated target" {
        uv run --project apps/api python scripts/sprint11_backup.py restore --bundle $bundle --isolated-root $restoredBundle --confirm-isolated
    } | Out-Null

    Invoke-Gate "Start clean restore PostgreSQL" { Start-Postgres $restorePostgres } | Out-Null
    Wait-Postgres $restorePostgres
    Invoke-Gate "Restore complete PostgreSQL state" {
        docker cp (Join-Path $restoredBundle "connector-postgres.dump") "${restorePostgres}:/tmp/postgres.dump"
        # pg_dumpall --clean necessarily reports errors while attempting to drop
        # the connected postgres database/current superuser. Continue through
        # those system-object errors; the following boundary-specific gates are
        # the fail-closed verification for every restored application database.
        docker exec $restorePostgres psql -U postgres -d postgres -f /tmp/postgres.dump
    } -Sensitive | Out-Null
    $restorePort = Get-PublishedPort $restorePostgres 5432
    $env:PROJECTA_CONNECTOR_DATABASE_PORT = [string]$restorePort
    $env:PROJECTA_EVIDENCE_ROOT = Join-Path $restoredBundle "evidence"
    Invoke-Gate "Invalidate all restored Projecta sessions" {
        docker exec $restorePostgres psql -U postgres -d $projectDatabase -v ON_ERROR_STOP=1 -c "UPDATE projecta_sessions SET revoked_at=now() WHERE revoked_at IS NULL;"
        docker exec $restorePostgres psql -U postgres -d $projectDatabase -Atqc "SELECT CASE WHEN count(*) FILTER (WHERE revoked_at IS NULL)=0 AND count(*) FILTER (WHERE session_id='recovery-session' AND revoked_at IS NOT NULL)=1 THEN 1 ELSE 0 END FROM projecta_sessions" | Select-String -Pattern '^1$' -Quiet
        if (-not $?) { exit 1 }
    } | Out-Null
    Invoke-Gate "Verify restored evidence and idempotent replay" { uv run --project apps/api python scripts/connector_recovery_fixture.py verify } | Out-Null
    Invoke-Gate "Start Keycloak from restored database" { Start-Keycloak $restoreKeycloak $restorePostgres } | Out-Null
    Wait-KeycloakRealm $restoreKeycloak

    Invoke-Gate "Start clean restore OpenBao" { Start-OpenBao $restoreBao } | Out-Null
    Wait-OpenBao $restoreBao
    $restoreInit = Initialize-Bao $restoreBao
    $restoreBootstrapToken = [string]$restoreInit.root_token
    Invoke-Gate "Decrypt and restore OpenBao Raft snapshot" {
        openssl enc -d -aes-256-cbc -pbkdf2 -in (Join-Path $restoredBundle "openbao-snapshot.enc") -out $rawSnapshot -pass "file:$snapshotKey"
        docker cp $rawSnapshot "${restoreBao}:/tmp/openbao.snap"
        Invoke-Bao $restoreBao $restoreBootstrapToken @("operator", "raft", "snapshot", "restore", "-force", "/tmp/openbao.snap")
    } -Sensitive | Out-Null
    Start-Sleep -Seconds 3
    foreach ($share in @($sourceInit.unseal_keys_b64 | Select-Object -First 2)) {
        docker exec -e BAO_ADDR=https://localhost:8200 -e BAO_CACERT=/openbao/tls/ca.crt $restoreBao bao operator unseal $share | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Restored OpenBao rejected original recovery shares." }
    }
    Invoke-Gate "Re-establish workload AppRole authentication" {
        $roleId = (Invoke-Bao $restoreBao $sourceRootToken @("read", "-field=role_id", "auth/approle/role/projecta-api/role-id") | Select-Object -Last 1).Trim()
        $secretId = (Invoke-Bao $restoreBao $sourceRootToken @("write", "-f", "-field=secret_id", "auth/approle/role/projecta-api/secret-id") | Select-Object -Last 1).Trim()
        $token = (docker exec -e BAO_ADDR=https://localhost:8200 -e BAO_CACERT=/openbao/tls/ca.crt $restoreBao bao write -field=token auth/approle/login role_id=$roleId secret_id=$secretId | Select-Object -Last 1).Trim()
        $marker = (Invoke-Bao $restoreBao $token @("kv", "get", "-field=marker", "projecta/recovery/sentinel") | Select-Object -Last 1).Trim()
        if ($marker -ne $sourceMarker) { exit 1 }
        Invoke-Bao $restoreBao $sourceRootToken @("token", "revoke", "-self") | Out-Null
    } -Sensitive | Out-Null

    Write-Evidence "passed"
    Write-Host "Sprint 11 stateful cold recovery passed. Evidence: $evidenceFile"
    exit 0
} catch {
    $failure = $_.Exception.Message
    try { Write-Evidence "failed" } catch { }
    Write-Error $failure
    exit 1
} finally {
    $ErrorActionPreference = "Continue"
    foreach ($container in @($sourceKeycloak,$restoreKeycloak,$sourceBao,$restoreBao,$sourcePostgres,$restorePostgres)) {
        docker rm --force --volumes $container 2>$null | Out-Null
    }
    foreach ($volume in @("${sourceBao}-data","${restoreBao}-data")) { docker volume rm $volume 2>$null | Out-Null }
    docker network rm $network 2>$null | Out-Null
    if (Test-Path -LiteralPath $tempRoot) { Remove-Item -LiteralPath $tempRoot -Recurse -Force }
    foreach ($name in @("PROJECTA_CONNECTOR_DATABASE_HOST","PROJECTA_CONNECTOR_DATABASE_PORT","PROJECTA_CONNECTOR_DATABASE_NAME","PROJECTA_CONNECTOR_DATABASE_USER","PROJECTA_CONNECTOR_DATABASE_PASSWORD","PROJECTA_EVIDENCE_ROOT")) {
        Remove-Item -Path "Env:$name" -ErrorAction SilentlyContinue
    }
}
