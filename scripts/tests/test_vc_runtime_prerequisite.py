from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


POWERSHELL = shutil.which("powershell.exe")
PREREQUISITE_SCRIPT = Path(__file__).resolve().parents[1] / "vc_runtime_prerequisite.ps1"


@pytest.mark.skipif(os.name != "nt" or POWERSHELL is None, reason="Windows PowerShell is required")
def test_prerequisite_version_publisher_and_installer_transitions() -> None:
    environment = os.environ.copy()
    environment["PROJECTA_TEST_VC_SCRIPT"] = str(PREREQUISITE_SCRIPT)
    command = r"""
 . $env:PROJECTA_TEST_VC_SCRIPT
$policy = [pscustomobject]@{
    installerFileName = 'VC_redist.x64.exe'
    minimumVersion = '14.42.34438.0'
    publisher = 'Microsoft Corporation'
    integrityContract = 'sha256-of-authenticode-verified-download-rechecked-before-launch'
}
$sha = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
$validMetadata = [pscustomobject]@{
    SignatureStatus = 'Valid'
    SignerName = 'Microsoft Corporation'
    SignerSubject = 'CN=Microsoft Corporation, O=Microsoft Corporation, C=US'
    OriginalFilename = 'VC_redist.x64.exe'
    ProductName = 'Microsoft Visual C++ 2015-2022 Redistributable (x64)'
    FileVersion = '14.42.34438.0'
    Sha256 = $sha
}
$currentMicrosoftProduct = $validMetadata.PSObject.Copy()
$currentMicrosoftProduct.ProductName = 'Microsoft Visual C++ v14 Redistributable (x64) - 14.51.36247'
$currentMicrosoftProduct.FileVersion = '14.51.36247.0'
$validRecord = [pscustomobject]@{
    Architecture = 'x64'; Installed = 1; Version = 'v14.42.34438.0'
    Major = 14; Minor = 42; Bld = 34438; Rbld = 0
}
$wrongPublisher = $validMetadata.PSObject.Copy()
$wrongPublisher.SignerName = 'Other Publisher'
$badSignature = $validMetadata.PSObject.Copy()
$badSignature.SignatureStatus = 'NotSigned'
$oldVersion = $validMetadata.PSObject.Copy()
$oldVersion.FileVersion = '14.41.34438.0'
$wrongArchitecture = $validMetadata.PSObject.Copy()
$wrongArchitecture.ProductName = 'Microsoft Visual C++ 2015-2022 Redistributable (ARM64)'
$badHash = $validMetadata.PSObject.Copy()
$badHash.Sha256 = 'not-a-sha256'
$wrongIntegrityPolicy = $policy.PSObject.Copy()
$wrongIntegrityPolicy.integrityContract = 'unverified'
$newerRecord = $validRecord.PSObject.Copy()
$newerRecord.Version = 'v14.50.35719.00'
$newerRecord.Minor = 50
$newerRecord.Bld = 35719
$newerRecord.Rbld = 0
$wrongRecord = $validRecord.PSObject.Copy()
$wrongRecord.Minor = 41
$wrongArchitectureRecord = $validRecord.PSObject.Copy()
$wrongArchitectureRecord.Architecture = 'x86'
$changedHash = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
$result = [pscustomobject]@{
    installedMinimum = Test-ProjectaInstalledVcRuntime -Record $validRecord -MinimumVersion '14.42.34438.0'
    installedNewer = Test-ProjectaInstalledVcRuntime -Record $newerRecord -MinimumVersion '14.42.34438.0'
    installedOlder = Test-ProjectaInstalledVcRuntime -Record $wrongRecord -MinimumVersion '14.42.34438.0'
    installedWrongArchitecture = Test-ProjectaInstalledVcRuntime -Record $wrongArchitectureRecord -MinimumVersion '14.42.34438.0'
    installerAccepted = (Test-ProjectaVcRedistMetadata -Metadata $validMetadata -Policy $policy).Accepted
    currentMicrosoftProductAccepted = (Test-ProjectaVcRedistMetadata -Metadata $currentMicrosoftProduct -Policy $policy).Accepted
    wrongPublisher = (Test-ProjectaVcRedistMetadata -Metadata $wrongPublisher -Policy $policy).Code
    badSignature = (Test-ProjectaVcRedistMetadata -Metadata $badSignature -Policy $policy).Code
    oldInstaller = (Test-ProjectaVcRedistMetadata -Metadata $oldVersion -Policy $policy).Code
    wrongArchitectureInstaller = (Test-ProjectaVcRedistMetadata -Metadata $wrongArchitecture -Policy $policy).Code
    badHash = (Test-ProjectaVcRedistMetadata -Metadata $badHash -Policy $policy).Code
    wrongIntegrityPolicy = (Test-ProjectaVcRedistMetadata -Metadata $validMetadata -Policy $wrongIntegrityPolicy).Code
    sameHash = Test-ProjectaVcInstallerHash -Expected $sha -Actual $sha.ToUpperInvariant()
    changedHashMatches = Test-ProjectaVcInstallerHash -Expected $sha -Actual $changedHash
    exits = @(
        (Convert-ProjectaVcInstallerResult -ExitCode 0 -RuntimeReady $true),
        (Convert-ProjectaVcInstallerResult -ExitCode 0 -RuntimeReady $false),
        (Convert-ProjectaVcInstallerResult -ExitCode 1602 -RuntimeReady $false),
        (Convert-ProjectaVcInstallerResult -ExitCode 3010 -RuntimeReady $true),
        (Convert-ProjectaVcInstallerResult -ExitCode 1641 -RuntimeReady $true),
        (Convert-ProjectaVcInstallerResult -ExitCode 1 -RuntimeReady $false)
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
        "installedMinimum": True,
        "installedNewer": True,
        "installedOlder": False,
        "installedWrongArchitecture": False,
        "installerAccepted": True,
        "currentMicrosoftProductAccepted": True,
        "wrongPublisher": "WrongPublisher",
        "badSignature": "InvalidSignature",
        "oldInstaller": "UnsupportedVersion",
        "wrongArchitectureInstaller": "UnsupportedPayload",
        "badHash": "InvalidIntegrity",
        "wrongIntegrityPolicy": "InvalidIntegrity",
        "sameHash": True,
        "changedHashMatches": False,
        "exits": ["Ready", "RuntimeNotReady", "Cancelled", "RestartRequired", "RestartRequired", "InstallerFailed"],
    }
