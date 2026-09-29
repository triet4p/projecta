param(
    [string]$EnvFile = (Join-Path $PSScriptRoot ".." ".env")
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$path = [System.IO.Path]::GetFullPath($EnvFile)
if ([string]::Equals($path, (Join-Path $root ".env.example"),
        [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "The tracked .env.example cannot hold generated credentials."
}
if (-not (Test-Path -LiteralPath $path)) {
    Copy-Item -LiteralPath (Join-Path $root ".env.example") -Destination $path
}
$lines = [System.Collections.Generic.List[string]]::new()
$lines.AddRange([string[]][System.IO.File]::ReadAllLines($path))
$changed = $false

function Get-LocalValue {
    param([string]$Name)
    $value = $null
    $escaped = [regex]::Escape($Name)
    foreach ($line in $lines) {
        if ($line -match "^\s*$escaped=(.*)$") {
            if ($null -ne $value) { throw "Duplicate setting: $Name" }
            $value = $Matches[1].Trim()
        }
    }
    return $value
}

function Set-LocalValue {
    param([string]$Name, [scriptblock]$Generate, [switch]$ReplaceHeadless)
    $current = Get-LocalValue $Name
    if ($null -ne $current -and $current -ne "" -and
        $current -notlike "replace-with-*" -and
        -not ($ReplaceHeadless -and $current -eq "headless")) {
        return
    }
    $value = & $Generate
    $escaped = [regex]::Escape($Name)
    for ($index = 0; $index -lt $lines.Count; $index++) {
        if ($lines[$index] -match "^\s*$escaped=") {
            $lines[$index] = "$Name=$value"
            $script:changed = $true
            return
        }
    }
    $lines.Add("$Name=$value")
    $script:changed = $true
}

function New-LocalKey {
    $bytes = [byte[]]::new(32)
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    return [Convert]::ToBase64String($bytes).Replace('+', '-').Replace('/', '_')
}

if ((Get-LocalValue "PROJECTA_API_RUNTIME_MODE") -eq "production") {
    throw "Local setup cannot change a production environment file."
}
Set-LocalValue "PROJECTA_CONNECTOR_POSTGRES_USER" { "projecta" }
Set-LocalValue "PROJECTA_CONNECTOR_POSTGRES_DB" { "projecta" }
Set-LocalValue "PROJECTA_CONNECTOR_POSTGRES_PASSWORD" { New-LocalKey }
Set-LocalValue "PROJECTA_API_TRUSTED_CONTEXT_SECRET" { New-LocalKey }
Set-LocalValue "PROJECTA_API_SECRET_STORE_MASTER_KEY" { New-LocalKey }
Set-LocalValue "PROJECTA_API_RUNTIME_MODE" { "experience" } -ReplaceHeadless
Set-LocalValue "PROJECTA_API_EXPERIENCE_ACTOR_ID" { "local-operator" }
Set-LocalValue "PROJECTA_API_EXPERIENCE_PROJECT_CATALOG" { "project-alpha,project-beta" }
Set-LocalValue "PROJECTA_BOOTSTRAP_ACCEPTANCE_PROJECTS" { "project-alpha|Project Alpha;project-beta|Project Beta" }

$key = Get-LocalValue "PROJECTA_API_SECRET_STORE_MASTER_KEY"
try {
    if ($key -notmatch '^[A-Za-z0-9_-]{43}=$' -or
        [Convert]::FromBase64String($key.Replace('-', '+').Replace('_', '/')).Length -ne 32) {
        throw "invalid key"
    }
} catch {
    throw "Existing PROJECTA_API_SECRET_STORE_MASTER_KEY is not a valid Fernet key; it was not replaced."
}

if ($changed) {
    [System.IO.File]::WriteAllLines($path, $lines, [System.Text.UTF8Encoding]::new($false))
}
Write-Host "Local environment is ready at $path. Credentials were not printed."
