param()

$ErrorActionPreference = 'Stop'
$systemTestProject = "projecta-system-test-$([guid]::NewGuid().ToString('N').Substring(0, 12))"
$composeArgs = @('-p', $systemTestProject, '--profile', 'system-test')
$exitCode = 0
$hadTrustedContextSecret = Test-Path Env:PROJECTA_API_TRUSTED_CONTEXT_SECRET
$previousTrustedContextSecret = $env:PROJECTA_API_TRUSTED_CONTEXT_SECRET
$runnerManagedSecret = $false
$hadMasterKey = Test-Path Env:PROJECTA_API_SECRET_STORE_MASTER_KEY
$previousMasterKey = $env:PROJECTA_API_SECRET_STORE_MASTER_KEY
$runnerManagedMasterKey = $false
$llmEnvironment = @{
    PROJECTA_LLM_TYPE = 'openai-response'
    PROJECTA_LLM_BASE_URL = 'https://system-test.invalid'
    PROJECTA_LLM_API_KEY = 'system-test-not-a-secret'
    PROJECTA_LLM_MODEL = 'replay:basic-requirement-001'
}
$previousLlmEnvironment = @{}

foreach ($entry in $llmEnvironment.GetEnumerator()) {
    $path = "Env:$($entry.Key)"
    $exists = Test-Path $path
    $previousLlmEnvironment[$entry.Key] = @{
        Exists = $exists
        Value = if ($exists) { (Get-Item $path).Value } else { $null }
    }
    Set-Item -Path $path -Value $entry.Value
}

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

    if ([string]::IsNullOrWhiteSpace($env:PROJECTA_API_SECRET_STORE_MASTER_KEY)) {
        $masterKeyBytes = New-Object byte[] 32
        $masterKeyGenerator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
        try {
            $masterKeyGenerator.GetBytes($masterKeyBytes)
        } finally {
            $masterKeyGenerator.Dispose()
        }
        $env:PROJECTA_API_SECRET_STORE_MASTER_KEY = [Convert]::ToBase64String($masterKeyBytes).Replace('+', '-').Replace('/', '_')
        $runnerManagedMasterKey = $true
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
    if ($exitCode -ne 0) {
        Write-Error "System test failed with exit code $exitCode. Capturing service logs before cleanup." -ErrorAction Continue
        & docker compose @composeArgs logs --no-color --tail 500 api-runtime-test semantic-core-runtime-test fuseki
    }
    & docker compose @composeArgs down --volumes --remove-orphans
    if ($exitCode -eq 0 -and $LASTEXITCODE -ne 0) { $exitCode = $LASTEXITCODE }

    foreach ($entry in $previousLlmEnvironment.GetEnumerator()) {
        $path = "Env:$($entry.Key)"
        if ($entry.Value.Exists) {
            Set-Item -Path $path -Value $entry.Value.Value
        } else {
            Remove-Item $path -ErrorAction SilentlyContinue
        }
    }
    if ($runnerManagedSecret) {
        if ($hadTrustedContextSecret) {
            $env:PROJECTA_API_TRUSTED_CONTEXT_SECRET = $previousTrustedContextSecret
        } else {
            Remove-Item Env:PROJECTA_API_TRUSTED_CONTEXT_SECRET -ErrorAction SilentlyContinue
        }
    }
    if ($runnerManagedMasterKey) {
        if ($hadMasterKey) {
            $env:PROJECTA_API_SECRET_STORE_MASTER_KEY = $previousMasterKey
        } else {
            Remove-Item Env:PROJECTA_API_SECRET_STORE_MASTER_KEY -ErrorAction SilentlyContinue
        }
    }
}

exit $exitCode
