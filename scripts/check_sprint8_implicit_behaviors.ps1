$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$sourceRoots = @(
    (Join-Path $root "apps\api\src"),
    (Join-Path $root "apps\web\src"),
    (Join-Path $root "apps\web\nginx.conf"),
    (Join-Path $root "services\semantic-core\src\main"),
    (Join-Path $root "compose.yaml")
)

function Assert-NoPattern([string] $Pattern, [string] $Description) {
    foreach ($sourceRoot in $sourceRoots) {
        $files = if (Test-Path -LiteralPath $sourceRoot -PathType Leaf) {
            @(Get-Item -LiteralPath $sourceRoot)
        } else {
            @(Get-ChildItem -LiteralPath $sourceRoot -Recurse -File -ErrorAction Stop |
                Where-Object { $_.Extension -in @('.py', '.ts', '.tsx', '.java', '.conf', '.yaml') })
        }
        foreach ($file in $files) {
            $content = Get-Content -LiteralPath $file.FullName -Raw
            if ([regex]::IsMatch($content, $Pattern)) {
                Write-Error "$($file.FullName): $Pattern"
                throw "Implicit-behavior regression: $Description"
            }
        }
    }
}

Assert-NoPattern 'os\.environ\.setdefault\(' 'authority-bearing environment defaults'
Assert-NoPattern 'local-project|local-user' 'fixed project/actor defaults in runtime source or Compose'
Assert-NoPattern 'response\.json\(\)\.catch\(\(\) => \(\{\}\)\)' 'empty success substitution after invalid JSON'
Assert-NoPattern 'ResilientGateway\([\s\S]{0,300}max_retries\s*=\s*[1-9]' 'implicit retry in application source'
Assert-NoPattern 'return\s+\{\s*"status"\s*:\s*"ready"\s*,\s*"semanticCore"\s*:\s*"injected"' 'synthetic readiness success'
Assert-NoPattern 'except\s+Exception\s*:\s*\r?\n\s*(pass|return)' 'catch-and-ignore path'
Assert-NoPattern '_propose_note_items|item_type\s*=\s*"research-need"' 'heuristic Note import fallback'
Assert-NoPattern '(setdefault\("(semanticType|lifecycleState|verificationState|provenanceState|relationType)"|get\("(semanticType|lifecycleState|verificationState|provenanceState|relationType)"\s*,\s*")' 'fabricated semantic projection state'
Assert-NoPattern 'getOrDefault\("(label|title|rawText|recordedAt|validFrom)"\s*,' 'fabricated Semantic Core projection values'
Assert-NoPattern 'placeholder="Opaque (link|actor) handle"' 'user-entered opaque handles'

$main = Get-Content (Join-Path $root "apps\api\src\projecta_api\main.py") -Raw
if ($main -notmatch 'mode="interactive-single-attempt"') {
    throw "Interactive gateway mode is not explicit."
}
if ($main -notmatch 'max_retries=0') {
    throw "Interactive gateway must have zero automatic retries."
}

Write-Output "Sprint 8 implicit-behavior regression gate passed."
