param(
    [string]$EvidencePath = "docs/sprint-plans/sprint-10/artifacts/s10-63-recovery.json"
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$runId = [guid]::NewGuid().ToString('N').Substring(0, 12)
$sourceName = "projecta-s10-recovery-source-$runId"
$restoreName = "projecta-s10-recovery-restore-$runId"
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) "projecta-s10-recovery-$runId"
$originalEvidence = Join-Path $tempRoot "original-evidence"
$backupRoot = Join-Path $tempRoot "backup"
$restoredRoot = Join-Path $tempRoot "restored"
$evidenceFile = Join-Path $root $EvidencePath
$password = "s10-recovery-$runId"
$sourcePort = $null
$restorePort = $null
$savedEnvironment = @{}
$results = [System.Collections.Generic.List[object]]::new()
$failure = $null

function Set-DatabaseEnvironment([int]$Port, [string]$EvidenceRoot) {
    $values = @{
        PROJECTA_CONNECTOR_DATABASE_HOST = "127.0.0.1"
        PROJECTA_CONNECTOR_DATABASE_PORT = [string]$Port
        PROJECTA_CONNECTOR_DATABASE_NAME = "projecta_recovery"
        PROJECTA_CONNECTOR_DATABASE_USER = "connector"
        PROJECTA_CONNECTOR_DATABASE_PASSWORD = $password
        PROJECTA_EVIDENCE_ROOT = $EvidenceRoot
    }
    foreach ($entry in $values.GetEnumerator()) {
        $path = "Env:$($entry.Key)"
        if (-not $savedEnvironment.ContainsKey($entry.Key)) {
            $savedEnvironment[$entry.Key] = @{
                Exists = Test-Path $path
                Value = if (Test-Path $path) { (Get-Item $path).Value } else { $null }
            }
        }
        Set-Item -Path $path -Value $entry.Value
    }
}

function Set-BackupEnvironment([int]$Port) {
    Set-Item Env:PROJECTA_CONNECTOR_BACKUP_DATABASE_URL "postgresql+psycopg://connector@127.0.0.1:$Port/projecta_recovery"
    Set-Item Env:PROJECTA_CONNECTOR_BACKUP_DATABASE_PASSWORD $password
    Set-Item Env:PROJECTA_CONNECTOR_BACKUP_TOOL_IMAGE "postgres:16.4-alpine"
}

function Restore-Environment {
    foreach ($entry in $savedEnvironment.GetEnumerator()) {
        $path = "Env:$($entry.Key)"
        if ($entry.Value.Exists) { Set-Item -Path $path -Value $entry.Value.Value }
        else { Remove-Item -Path $path -ErrorAction SilentlyContinue }
    }
    foreach ($name in @("PROJECTA_CONNECTOR_BACKUP_DATABASE_URL", "PROJECTA_CONNECTOR_BACKUP_DATABASE_PASSWORD", "PROJECTA_CONNECTOR_BACKUP_TOOL_IMAGE")) {
        Remove-Item -Path "Env:$name" -ErrorAction SilentlyContinue
    }
}

function Invoke-Checked([string]$Name, [scriptblock]$Command) {
    Write-Host "[S10-63] $Name"
    $start = [DateTime]::UtcNow
    $previousErrorActionPreference = $ErrorActionPreference
    $previousNativePreference = $PSNativeCommandUseErrorActionPreference
    try {
        # Python migration/backup tools may use stderr for normal progress output.
        $ErrorActionPreference = "Continue"
        $PSNativeCommandUseErrorActionPreference = $false
        $output = @(& $Command 2>&1 | ForEach-Object { [string]$_ })
        $exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { [int]$LASTEXITCODE }
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
        $PSNativeCommandUseErrorActionPreference = $previousNativePreference
    }
    $results.Add([pscustomobject]@{
        name = $Name
        startedAt = $start.ToString("o")
        finishedAt = [DateTime]::UtcNow.ToString("o")
        exitCode = $exitCode
        output = @($output | Select-Object -Last 50)
    })
    $output | Select-Object -Last 10 | ForEach-Object { Write-Host $_ }
    if ($exitCode -ne 0) { throw "$Name failed with exit code $exitCode." }
    return $output
}

function Wait-Postgres([string]$Name) {
    $deadline = (Get-Date).AddSeconds(90)
    do {
        try {
            docker exec $Name pg_isready -U connector -d projecta_recovery | Out-Null
            if ($LASTEXITCODE -eq 0) { return }
        } catch { }
        if ((Get-Date) -gt $deadline) { throw "$Name did not become ready." }
        Start-Sleep -Seconds 2
    } while ($true)
}

function Get-HostPort([string]$Name) {
    $mapping = docker port $Name 5432/tcp
    if ($LASTEXITCODE -ne 0 -or $mapping -notmatch ":(?<port>\d+)") { throw "Could not resolve the temporary PostgreSQL port." }
    return [int]$Matches["port"]
}

function Write-Evidence([string]$Status) {
    New-Item -ItemType Directory -Path (Split-Path -Parent $evidenceFile) -Force | Out-Null
    [pscustomobject]@{
        schemaVersion = "s10.recovery.v1"
        status = $Status
        sourceContainer = $sourceName
        restoreContainer = $restoreName
        backupVersion = "connector-backup.v1"
        failure = $failure
        results = @($results)
    } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $evidenceFile -Encoding utf8
}

try {
    New-Item -ItemType Directory -Path $originalEvidence,$backupRoot,$tempRoot -Force | Out-Null
    $savedEnvironment["POSTGRES_PASSWORD"] = @{
        Exists = Test-Path Env:POSTGRES_PASSWORD
        Value = if (Test-Path Env:POSTGRES_PASSWORD) { $env:POSTGRES_PASSWORD } else { $null }
    }
    Set-Item Env:POSTGRES_PASSWORD $password
    Invoke-Checked "Start isolated source PostgreSQL" {
        docker run --detach --name $sourceName --publish-all --env POSTGRES_USER=connector --env POSTGRES_PASSWORD --env POSTGRES_DB=projecta_recovery postgres:16.4-alpine
    }
    Wait-Postgres $sourceName
    $sourcePort = Get-HostPort $sourceName
    Set-DatabaseEnvironment $sourcePort $originalEvidence
    Invoke-Checked "Apply connector migrations" {
        uv run --project apps/api python -m projecta_api.operational.migrate upgrade
    }
    Invoke-Checked "Seed source installation/run/cursor/evidence" {
        uv run --project apps/api python scripts/connector_recovery_fixture.py seed
    }
    Set-BackupEnvironment $sourcePort
    $backupPath = Join-Path $backupRoot "backup"
    Invoke-Checked "Create PostgreSQL/evidence backup" {
        uv run --project apps/api python scripts/connector_backup.py backup --output $backupPath --evidence-root $originalEvidence --confirm-quiesced
    }
    Invoke-Checked "Teardown source stack" {
        docker rm --force --volumes $sourceName
    }
    Invoke-Checked "Start isolated clean restore PostgreSQL" {
        docker run --detach --name $restoreName --publish-all --env POSTGRES_USER=connector --env POSTGRES_PASSWORD --env POSTGRES_DB=projecta_recovery postgres:16.4-alpine
    }
    Wait-Postgres $restoreName
    $restorePort = Get-HostPort $restoreName
    Set-BackupEnvironment $restorePort
    $restoreEvidence = Join-Path $restoredRoot "restore"
    Invoke-Checked "Restore backup into isolated target" {
        uv run --project apps/api python scripts/connector_recovery_drill.py --backup $backupPath --isolated-root $restoreEvidence --confirm-isolated
    }
    Set-DatabaseEnvironment $restorePort (Join-Path $restoreEvidence "evidence")
    Invoke-Checked "Verify restored state and replay" {
        uv run --project apps/api python scripts/connector_recovery_fixture.py verify
    }
    $previousErrorActionPreference = $ErrorActionPreference
    $previousNativePreference = $PSNativeCommandUseErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $PSNativeCommandUseErrorActionPreference = $false
        $logs = docker logs $restoreName 2>&1 | Out-String
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
        $PSNativeCommandUseErrorActionPreference = $previousNativePreference
    }
    if ($logs.Contains($password) -or $logs.Contains("secretReference")) { throw "Recovery PostgreSQL logs leaked a forbidden value." }
    Write-Evidence "passed"
    Write-Host "Sprint 10 isolated recovery passed. Evidence: $evidenceFile"
    exit 0
} catch {
    $failure = $_.Exception.Message
    try { Write-Evidence "failed" } catch { Write-Error "Could not write recovery evidence: $($_.Exception.Message)" }
    Write-Error $failure
    exit 1
} finally {
    $cleanupErrorActionPreference = $ErrorActionPreference
    $cleanupNativePreference = $PSNativeCommandUseErrorActionPreference
    $ErrorActionPreference = "Continue"
    $PSNativeCommandUseErrorActionPreference = $false
    try {
        foreach ($name in @($sourceName, $restoreName)) {
            docker rm --force --volumes $name 2>$null | Out-Null
        }
    } finally {
        $ErrorActionPreference = $cleanupErrorActionPreference
        $PSNativeCommandUseErrorActionPreference = $cleanupNativePreference
    }
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
    Restore-Environment
}
