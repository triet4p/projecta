param(
    [Parameter(Mandatory = $true)]
    [string]$Secret
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($Secret)) { throw "A non-empty regression-test secret is required." }
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$scanRoots = @(
    (Join-Path $root "apps\web\dist"),
    (Join-Path $root "apps\web\src"),
    (Join-Path $root "apps\api\tests"),
    (Join-Path $root "evaluation"),
    (Join-Path $root "ontology"),
    (Join-Path $root "docs\sprint-plans\sprint-7")
)
$matches = @()
foreach ($scanRoot in $scanRoots) {
    if (Test-Path -LiteralPath $scanRoot) {
        $matches += Get-ChildItem -LiteralPath $scanRoot -File -Recurse | Select-String -SimpleMatch $Secret
    }
}
if ($matches.Count -gt 0) {
    $matches | ForEach-Object { Write-Error $_.ToString() }
    throw "Secret leak regression failed."
}
Write-Host "No regression-test secret found in source, built assets, fixtures, ontology, or review artifacts."
