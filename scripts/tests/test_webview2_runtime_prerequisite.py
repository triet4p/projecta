from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


POWERSHELL = shutil.which("powershell.exe")
PREREQUISITE_SCRIPT = Path(__file__).resolve().parents[1] / "webview2_runtime_prerequisite.ps1"


@pytest.mark.skipif(os.name != "nt" or POWERSHELL is None, reason="Windows PowerShell is required")
def test_webview2_detection_version_publisher_and_installer_transitions() -> None:
    environment = os.environ.copy()
    environment["PROJECTA_TEST_WEBVIEW2_SCRIPT"] = str(PREREQUISITE_SCRIPT)
    command = r"""
 . $env:PROJECTA_TEST_WEBVIEW2_SCRIPT
$policy = [pscustomobject]@{
    installerFileName = 'MicrosoftEdgeWebview2Setup.exe'
    minimumVersion = '109.0.1518.78'
    publisher = 'Microsoft Corporation'
    integrityContract = 'sha256-of-authenticode-verified-download-rechecked-before-launch'
}
$sha = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
$validMetadata = [pscustomobject]@{
    SignatureStatus = 'Valid'
    SignerName = 'Microsoft Corporation'
    SignerSubject = 'CN=Microsoft Corporation, O=Microsoft Corporation, C=US'
    OriginalFilename = 'MicrosoftEdgeWebview2Setup.exe'
    ProductName = 'Microsoft Edge WebView2 Evergreen Bootstrapper'
    FileVersion = '1.3.287.9'
    Sha256 = $sha
}
$wrongPublisher = $validMetadata.PSObject.Copy()
$wrongPublisher.SignerName = 'Other Publisher'
$badSignature = $validMetadata.PSObject.Copy()
$badSignature.SignatureStatus = 'NotSigned'
$wrongFile = $validMetadata.PSObject.Copy()
$wrongFile.OriginalFilename = 'VC_redist.x64.exe'
$badHash = $validMetadata.PSObject.Copy()
$badHash.Sha256 = 'not-a-sha256'
$wrongIntegrityPolicy = $policy.PSObject.Copy()
$wrongIntegrityPolicy.integrityContract = 'unverified'
$changedHash = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
$result = [pscustomobject]@{
    parseMinimum = ($null -ne (ConvertTo-ProjectaWebView2Version '109.0.1518.78'))
    parseMalformed = ($null -eq (ConvertTo-ProjectaWebView2Version 'not-a-version'))
    parseZero = ($null -ne (ConvertTo-ProjectaWebView2Version '0.0.0.0'))
    installedMinimum = Test-ProjectaWebView2Version -Value '109.0.1518.78' -MinimumVersion '109.0.1518.78'
    installedNewer = Test-ProjectaWebView2Version -Value '155.0.4283.45' -MinimumVersion '109.0.1518.78'
    installedOlder = Test-ProjectaWebView2Version -Value '108.0.1462.54' -MinimumVersion '109.0.1518.78'
    installedZeroIsMissing = Test-ProjectaWebView2Version -Value '0.0.0.0' -MinimumVersion '109.0.1518.78'
    installedEmptyIsMissing = Test-ProjectaWebView2Version -Value '' -MinimumVersion '109.0.1518.78'
    installedMalformedIsMissing = Test-ProjectaWebView2Version -Value 'not-a-version' -MinimumVersion '109.0.1518.78'
    setPrefersNewest = (Test-ProjectaInstalledWebView2Runtime -Versions @('109.0.1518.78', '155.0.4283.45') -MinimumVersion '109.0.1518.78')
    setOlderOnly = (Test-ProjectaInstalledWebView2Runtime -Versions @('108.0.1462.54') -MinimumVersion '109.0.1518.78')
    setEmpty = (Test-ProjectaInstalledWebView2Runtime -Versions @() -MinimumVersion '109.0.1518.78')
    setNull = (Test-ProjectaInstalledWebView2Runtime -Versions $null -MinimumVersion '109.0.1518.78')
    installerAccepted = (Test-ProjectaWebView2BootstrapperMetadata -Metadata $validMetadata -Policy $policy).Accepted
    wrongPublisher = (Test-ProjectaWebView2BootstrapperMetadata -Metadata $wrongPublisher -Policy $policy).Code
    badSignature = (Test-ProjectaWebView2BootstrapperMetadata -Metadata $badSignature -Policy $policy).Code
    wrongFile = (Test-ProjectaWebView2BootstrapperMetadata -Metadata $wrongFile -Policy $policy).Code
    badHash = (Test-ProjectaWebView2BootstrapperMetadata -Metadata $badHash -Policy $policy).Code
    wrongIntegrityPolicy = (Test-ProjectaWebView2BootstrapperMetadata -Metadata $validMetadata -Policy $wrongIntegrityPolicy).Code
    sameHash = Test-ProjectaWebView2InstallerHash -Expected $sha -Actual $sha.ToUpperInvariant()
    changedHashMatches = Test-ProjectaWebView2InstallerHash -Expected $sha -Actual $changedHash
    exits = @(
        (Convert-ProjectaWebView2InstallerResult -ExitCode 0 -RuntimeReady $true),
        (Convert-ProjectaWebView2InstallerResult -ExitCode 0 -RuntimeReady $false),
        (Convert-ProjectaWebView2InstallerResult -ExitCode 1602 -RuntimeReady $false),
        (Convert-ProjectaWebView2InstallerResult -ExitCode 3010 -RuntimeReady $true),
        (Convert-ProjectaWebView2InstallerResult -ExitCode 1641 -RuntimeReady $true),
        (Convert-ProjectaWebView2InstallerResult -ExitCode 1 -RuntimeReady $false)
    )
}
ConvertTo-Json -InputObject $result -Depth 4 -Compress
"""
    completed = subprocess.run(
        [POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result == {
        "parseMinimum": True,
        "parseMalformed": True,
        "parseZero": True,
        "installedMinimum": True,
        "installedNewer": True,
        "installedOlder": False,
        "installedZeroIsMissing": False,
        "installedEmptyIsMissing": False,
        "installedMalformedIsMissing": False,
        "setPrefersNewest": True,
        "setOlderOnly": False,
        "setEmpty": False,
        "setNull": False,
        "installerAccepted": True,
        "wrongPublisher": "WrongPublisher",
        "badSignature": "InvalidSignature",
        "wrongFile": "UnsupportedPayload",
        "badHash": "InvalidIntegrity",
        "wrongIntegrityPolicy": "InvalidIntegrity",
        "sameHash": True,
        "changedHashMatches": False,
        "exits": ["Ready", "RuntimeNotReady", "Cancelled", "RestartRequired", "RestartRequired", "InstallerFailed"],
    }
