param(
    [switch]$SkipCompose,
    [switch]$RunLive
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

Push-Location $root
try {
    Push-Location (Join-Path $root 'apps/api')
    try {
        uv run pytest -q
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        uv run ruff check src tests
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        uv run pyright
    } finally {
        Pop-Location
    }
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Push-Location (Join-Path $root 'apps/api')
    try {
        uv run python ../../evaluation/sprint-5/run_offline.py
    } finally {
        Pop-Location
    }
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    if ($RunLive) {
        $envFile = Join-Path $root '.env'
        if (Test-Path -LiteralPath $envFile -PathType Leaf) {
            foreach ($name in @('PROJECTA_LLM_TYPE', 'PROJECTA_LLM_BASE_URL', 'PROJECTA_LLM_API_KEY', 'PROJECTA_LLM_MODEL')) {
                if (-not (Test-Path ("Env:" + $name))) {
                    $line = Get-Content -LiteralPath $envFile | Where-Object { $_ -match "^$name=" } | Select-Object -Last 1
                    if ($null -ne $line) {
                        Set-Item -Path ("Env:" + $name) -Value $line.Substring($name.Length + 1).Trim().Trim('"')
                    }
                }
            }
        }
        Push-Location (Join-Path $root 'apps/api')
        try {
            uv run python ../../evaluation/sprint-5/run_live.py
        } finally {
            Pop-Location
        }
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }

    if (-not $SkipCompose) {
        & $PSScriptRoot/run_system_tests.ps1
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
} finally {
    Pop-Location
}
