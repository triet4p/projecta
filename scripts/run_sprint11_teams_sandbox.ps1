param([string]$ApiBaseUrl = $env:PROJECTA_TEAMS_SANDBOX_API_URL, [string]$ProjectHandle = $env:PROJECTA_TEAMS_SANDBOX_PROJECT_HANDLE, [string]$SetupHandle = $env:PROJECTA_TEAMS_SANDBOX_SETUP_HANDLE, [string]$EvidencePath = "docs/sprint-plans/sprint-11/artifacts/s11-67-live-sandbox.json")

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($ApiBaseUrl) -or [string]::IsNullOrWhiteSpace($ProjectHandle) -or [string]::IsNullOrWhiteSpace($SetupHandle)) { throw "S11-67 requires operator-provided API URL, project handle, and opaque setup handle; no credential argument is accepted." }
$headers = @{ "Idempotency-Key" = "s11-live-$([guid]::NewGuid().ToString('N'))" }
$base = "$ApiBaseUrl/v1/projects/$([uri]::EscapeDataString($ProjectHandle))/connectors/installations"
$sanitized = [System.Collections.Generic.List[object]]::new()
$installation = $null
try {
    $installation = Invoke-RestMethod -Method Post -Uri $base -Headers $headers -ContentType "application/json" -Body (@{ connectorType = "teams"; teamsSetupHandle = $SetupHandle; capabilities = @("inbound-import") } | ConvertTo-Json)
    $sanitized.Add(@{ step = "create"; state = $installation.setupStatus; revision = $installation.revision })
    $handle = $installation.handle
    $enabled = Invoke-RestMethod -Method Post -Uri "$base/$handle/enable" -ContentType "application/json" -Body (@{ expectedInstallationRevision = $installation.revision } | ConvertTo-Json)
    $sanitized.Add(@{ step = "enable"; enabled = $enabled.enabled; revision = $enabled.revision })
    $run = Invoke-RestMethod -Method Post -Uri "$base/$handle/runs" -Headers $headers -ContentType "application/json" -Body (@{ expectedInstallationRevision = $enabled.revision } | ConvertTo-Json)
    $sanitized.Add(@{ step = "run"; state = $run.state; eventCount = $run.eventCount; replayCount = $run.replayCount })
    $disabled = Invoke-RestMethod -Method Post -Uri "$base/$handle/disable" -ContentType "application/json" -Body (@{ expectedInstallationRevision = $enabled.revision } | ConvertTo-Json)
    $sanitized.Add(@{ step = "revoke"; enabled = $disabled.enabled; revision = $disabled.revision })
    $status = "passed"
} catch { $status = "failed"; $failure = $_.Exception.Message }
finally {
    $path = Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..")).Path $EvidencePath
    New-Item -ItemType Directory -Path (Split-Path -Parent $path) -Force | Out-Null
    @{ schemaVersion = "sprint11.live-teams.v1"; status = $status; failure = if ($failure) { "sandbox operation failed" } else { $null }; steps = @($sanitized); rawProviderPayload = $false; credentialsPersisted = $false } | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $path -Encoding utf8
}
if ($status -ne "passed") { exit 1 }
