param([switch]$Force)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if ($null -eq (Get-Command openssl -ErrorAction SilentlyContinue)) {
    throw "OpenSSL is required to generate isolated acceptance certificates."
}

function Invoke-OpenSsl {
    param([string[]]$Arguments)
    & openssl @Arguments 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "OpenSSL acceptance certificate generation failed."
    }
}

function New-SelfSignedServerCertificate {
    param(
        [string]$Directory,
        [string]$CertificateName,
        [string]$KeyName,
        [string]$CommonName,
        [string]$SubjectAlternativeNames
    )
    New-Item -ItemType Directory -Path $Directory -Force | Out-Null
    $certificate = Join-Path $Directory $CertificateName
    $key = Join-Path $Directory $KeyName
    if (-not $Force -and ((Test-Path -LiteralPath $certificate) -or (Test-Path -LiteralPath $key))) {
        throw "Acceptance TLS output already exists; use -Force only for disposable rotation."
    }
    Invoke-OpenSsl @(
        "req", "-x509", "-newkey", "rsa:2048", "-sha256", "-days", "7", "-nodes",
        "-keyout", $key, "-out", $certificate, "-subj", "/CN=$CommonName",
        "-addext", "subjectAltName=$SubjectAlternativeNames",
        "-addext", "keyUsage=critical,digitalSignature,keyEncipherment",
        "-addext", "extendedKeyUsage=serverAuth"
    )
}

$openBaoDirectory = Join-Path $root "infra/openbao/tls"
New-SelfSignedServerCertificate $openBaoDirectory "tls.crt" "tls.key" "openbao" "DNS:openbao,DNS:localhost,IP:127.0.0.1"
Copy-Item -LiteralPath (Join-Path $openBaoDirectory "tls.crt") -Destination (Join-Path $openBaoDirectory "ca.crt") -Force

$keycloakDirectory = Join-Path $root "infra/keycloak/tls"
New-SelfSignedServerCertificate $keycloakDirectory "tls.crt" "tls.key" "auth.example.com" "DNS:auth.example.com,DNS:keycloak,DNS:localhost,IP:127.0.0.1"
Copy-Item -LiteralPath (Join-Path $keycloakDirectory "tls.crt") -Destination (Join-Path $keycloakDirectory "ca.crt") -Force

$edgeDirectory = Join-Path $root "infra/edge/tls"
New-SelfSignedServerCertificate $edgeDirectory "projecta.crt" "projecta.key" "projecta.example.com" "DNS:projecta.example.com,DNS:localhost,IP:127.0.0.1"
New-SelfSignedServerCertificate $edgeDirectory "auth.crt" "auth.key" "auth.example.com" "DNS:auth.example.com,DNS:localhost,IP:127.0.0.1"

Write-Host "Generated seven-day acceptance-only TLS material in git-ignored operator paths."
