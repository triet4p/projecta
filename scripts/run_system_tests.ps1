param()

$ErrorActionPreference = 'Stop'
$systemTestProject = "projecta-system-test-$([guid]::NewGuid().ToString('N').Substring(0, 12))"
$composeArgs = @('-p', $systemTestProject, '--profile', 'system-test')
$exitCode = 0
$hadTrustedContextSecret = Test-Path Env:PROJECTA_API_TRUSTED_CONTEXT_SECRET
$previousTrustedContextSecret = $env:PROJECTA_API_TRUSTED_CONTEXT_SECRET
$runnerManagedSecret = $false

function Get-DotEnvTrustedContextSecret {
    $envFile = Join-Path (Split-Path -Parent $PSScriptRoot) '.env'
    if (-not (Test-Path -LiteralPath $envFile -PathType Leaf)) {
        return $null
    }

    foreach ($line in Get-Content -LiteralPath $envFile) {
        if ($line -match '^\s*PROJECTA_API_TRUSTED_CONTEXT_SECRET\s*=\s*(?<value>.*)\s*$') {
            $value = $Matches['value'].Trim()
            if ($value.Length -ge 2 -and $value.StartsWith('"') -and $value.EndsWith('"')) {
                $value = $value.Substring(1, $value.Length - 2)
            }
            if (-not [string]::IsNullOrWhiteSpace($value)) {
                return $value
            }
        }
    }

    return $null
}

try {
    $processSecret = $env:PROJECTA_API_TRUSTED_CONTEXT_SECRET
    $dotEnvSecret = if ([string]::IsNullOrWhiteSpace($processSecret)) {
        Get-DotEnvTrustedContextSecret
    } else {
        $null
    }

    if ([string]::IsNullOrWhiteSpace($processSecret) -and [string]::IsNullOrWhiteSpace($dotEnvSecret)) {
        $bytes = New-Object byte[] 32
        $randomNumberGenerator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
        try {
            $randomNumberGenerator.GetBytes($bytes)
        } finally {
            $randomNumberGenerator.Dispose()
        }
        $generatedSecret = ($bytes | ForEach-Object { $_.ToString('x2') }) -join ''
        $env:PROJECTA_API_TRUSTED_CONTEXT_SECRET = $generatedSecret
        $runnerManagedSecret = $true
    } elseif ([string]::IsNullOrWhiteSpace($processSecret) -and $hadTrustedContextSecret) {
        Remove-Item Env:PROJECTA_API_TRUSTED_CONTEXT_SECRET
        $runnerManagedSecret = $true
    }

    & docker compose @composeArgs --profile tools run --build --rm ontology-test
    if ($LASTEXITCODE -ne 0) { $exitCode = $LASTEXITCODE }

    if ($exitCode -eq 0) {
        & docker compose @composeArgs run --build --rm semantic-core-system-test
        if ($LASTEXITCODE -ne 0) { $exitCode = $LASTEXITCODE }
    }

    if ($exitCode -eq 0) {
        & docker compose @composeArgs run --build --rm api-system-test
        if ($LASTEXITCODE -ne 0) { $exitCode = $LASTEXITCODE }
    }
}
finally {
    if ($runnerManagedSecret) {
        if ($hadTrustedContextSecret) {
            $env:PROJECTA_API_TRUSTED_CONTEXT_SECRET = $previousTrustedContextSecret
        } else {
            Remove-Item Env:PROJECTA_API_TRUSTED_CONTEXT_SECRET -ErrorAction SilentlyContinue
        }
    }
    & docker compose @composeArgs down --volumes --remove-orphans
    if ($exitCode -eq 0 -and $LASTEXITCODE -ne 0) { $exitCode = $LASTEXITCODE }
}

exit $exitCode
