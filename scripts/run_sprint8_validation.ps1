param(
    [switch]$RunOntology
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$apiRoot = (Resolve-Path (Join-Path $root "apps/api")).Path
$webRoot = (Resolve-Path (Join-Path $root "apps/web")).Path

function Invoke-Checked([string]$Label, [scriptblock]$Command) {
    Write-Host "[S8-66] $Label"
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$Label failed with exit code $LASTEXITCODE." }
}

Push-Location $root
try {
    Push-Location $apiRoot
    try {
        Invoke-Checked "Python lint" { uv run ruff check . }
        Invoke-Checked "Full Python type check" {
            uv run pyright
        }
        Invoke-Checked "Python regression suite" { uv run pytest -q }
    } finally { Pop-Location }

    Push-Location (Join-Path $root "services/semantic-core")
    try {
        Invoke-Checked "Semantic Core verification" { mvn --batch-mode verify }
    } finally { Pop-Location }

    Push-Location $webRoot
    try {
        Invoke-Checked "Frontend type check" { npm run typecheck }
        Invoke-Checked "Frontend lint" { npm run lint }
        Invoke-Checked "Frontend unit/contract tests" { npm test }
        Invoke-Checked "Nginx configuration contract" { npm run check:nginx-config }
        Invoke-Checked "Application API drift gate" { npm run check:api-drift }
        Invoke-Checked "Frontend production build" { npm run build }
    } finally { Pop-Location }

    Invoke-Checked "UI contract checker" { node (Join-Path $root ".agents/skills/build-databricks-ui/scripts/check-ui-contract.mjs") (Join-Path $webRoot "src/styles.css") }
    Invoke-Checked "Implicit-behavior regression gate" { & (Join-Path $root "scripts/check_sprint8_implicit_behaviors.ps1") }
    Invoke-Checked "Compose health contract" { & (Join-Path $root "scripts/check_sprint8_health_contract.ps1") }
    Invoke-Checked "Diff whitespace check" { git diff --check }

    if ($RunOntology) {
        $hadMasterKey = Test-Path Env:PROJECTA_API_SECRET_STORE_MASTER_KEY
        $previousMasterKey = if ($hadMasterKey) { $env:PROJECTA_API_SECRET_STORE_MASTER_KEY } else { $null }
        $hadTrustedSecret = Test-Path Env:PROJECTA_API_TRUSTED_CONTEXT_SECRET
        $previousTrustedSecret = if ($hadTrustedSecret) { $env:PROJECTA_API_TRUSTED_CONTEXT_SECRET } else { $null }
        try {
            if (-not $hadMasterKey) { $env:PROJECTA_API_SECRET_STORE_MASTER_KEY = "validation-only" }
            if (-not $hadTrustedSecret) { $env:PROJECTA_API_TRUSTED_CONTEXT_SECRET = "validation-only-trusted-context" }
            Invoke-Checked "Ontology validation container" { docker compose -f compose.yaml --profile tools run --build --rm ontology-test }
        } finally {
            if ($hadMasterKey) { $env:PROJECTA_API_SECRET_STORE_MASTER_KEY = $previousMasterKey }
            else { Remove-Item Env:PROJECTA_API_SECRET_STORE_MASTER_KEY -ErrorAction SilentlyContinue }
            if ($hadTrustedSecret) { $env:PROJECTA_API_TRUSTED_CONTEXT_SECRET = $previousTrustedSecret }
            else { Remove-Item Env:PROJECTA_API_TRUSTED_CONTEXT_SECRET -ErrorAction SilentlyContinue }
        }
    } else {
        Write-Output "Ontology container validation was not requested; use -RunOntology when Docker is available."
    }
}
finally { Pop-Location }
