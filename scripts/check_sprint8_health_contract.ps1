$ErrorActionPreference = "Stop"

$compose = Get-Content (Join-Path $PSScriptRoot "..\compose.yaml") -Raw
if ($compose -notmatch "health/ready'\)\.status == 200") {
    throw "API Compose healthcheck must probe readiness, not liveness."
}
if ($compose -notmatch "start_period:") {
    throw "Compose healthchecks must declare start_period."
}
if ($compose -notmatch "health/ready") {
    throw "Compose must contain a readiness probe."
}

Write-Output "Sprint 8 Compose health contract verified."
