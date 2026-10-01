# Projecta 0.7.0 unsigned test pre-release — Windows 11 x64

This is the owner-authorized unsigned 0.7.0 test pre-release, not a signed
release, production installation, or clean-Windows certification. Windows
cannot verify the publisher; SmartScreen or antivirus software may warn or
block the file. Never disable security controls or bypass a Windows block.
This exception applies only to 0.7.0. Signed release and update verification
remain fail-closed.

The installer bundles the local Python 3.12 and Java 21 runtimes, PostgreSQL,
Fuseki/TDB2, Semantic Core, API, and web assets. You do not need Docker,
Python, Node.js, a JDK, PostgreSQL, or Fuseki installed separately; startup
does not pull runtime images or dependencies. The browser is not bundled;
Projecta opens the current Windows account's default browser.

## Get and verify the installer

The owner-authorized 0.7.0 Windows 11 x64 test pre-release is intended to
have one installer asset; it is unsigned and is not a signed release,
production installation, or clean-Windows certification. The GitHub release
page has not yet been published, so this handoff has no public download URL.
Do not substitute a repository checkout, `build` folder, package archive, or
other installer candidate for the exact asset when the owner publishes it.

Expected installer filename:

`Projecta-Setup-0.7.0-win-x64-unsigned-prerelease.exe`

Size: **119,495,860 bytes**.

SHA-256:

`f7555a90807bff34540a89758e5f8fe5853b8cbd09d3772d40ac4c9d77a64a77`

Build provenance from the receipts: package source and installer source
revision `674d0cb3e76096a60725556b20be3767e2508e28`; the installer is
**NotSigned**. The build-only package archive
`ProjectaLocal-0.7.0-win-x64-unsigned-pre-release-test-fixed.zip` is
191,750,058 bytes, SHA-256
`373a4c4aec1ba89f24f68934d4465a7a4be441887c6a21ca327572ac6304bd65`.
That archive is provenance only, not a second user download.

After the exact asset is available from the owner-approved release, compare
its filename, size, and checksum before opening it. In Command Prompt:

```cmd
certutil -hashfile "%USERPROFILE%\Downloads\Projecta-Setup-0.7.0-win-x64-unsigned-prerelease.exe" SHA256
```

Proceed only if the downloaded file matches all three values above and came
from the owner-approved asset. If the asset or checksum is unavailable, stop
and wait. Windows cannot verify the publisher; SmartScreen or antivirus may
warn or block the file. Never disable security controls or use a “run anyway”
bypass.

## Install and start

1. Sign in to the Windows 11 x64 account that will use Projecta. This is a
   per-user install and does not need administrator privileges. Do not choose
   **Run as administrator**.
2. Double-click the verified `.exe`. Read the unsigned-test warning and
   continue only after verifying the asset; otherwise cancel.
3. Keep the default `%LOCALAPPDATA%\Programs\Projecta\0.7.0` location and
   finish the wizard. Choose **Open Projecta** on the finish page.
4. In the **Create your workspace** dialog, enter a display name of 1–128
   characters and choose **OK**. Wait for **Ready — all four local services
   are running** and confirm PostgreSQL, Fuseki, Semantic Core, and API each
   show **Running**. The default browser opens `http://127.0.0.1:18732/`;
   use **Open Projecta in browser** in the panel if needed.

The fixed package rendered this first-run dialog, but automated interaction
could not submit the workspace form. The actual desktop first-run completion
and its ready state remain unverified; this exact interactive check is still
required. It is not a clean-Windows proof or a selected product-journey pass.

Later, open **Projecta** from the current user's Start menu to launch the
desktop control panel. Use **Start Projecta** to start the local runtime and
**Open Projecta in browser** to reopen the loopback page. The panel shows
overall readiness plus per-service status. To stop cleanly, choose **Stop
services** and wait until all four service rows show **Stopped**. If the panel
asks whether to keep services running, choose **No** to return to the panel
and stop them first; choose **Yes** only when background operation is
intentional.

## Data, uninstall, and reporting

Application files are under `%LOCALAPPDATA%\Programs\Projecta\0.7.0`.
Workspace configuration, DPAPI-protected secrets, databases, evidence, and
logs are kept separately under `%LOCALAPPDATA%\Projecta`. The safe launcher
log is `%LOCALAPPDATA%\Projecta\logs\launcher.log`.

If startup fails, note the displayed error code and use **Open safe diagnostics
folder** in the panel. Preserve the entire `%LOCALAPPDATA%\Projecta` data
directory; do not delete databases, secrets, configuration, evidence, or logs
to silence an error. Stop the services if the panel remains responsive and
report only the error code and sanitized symptoms.

Back up any wanted data before uninstalling. Stop all four services, then use
**Settings → Apps → Installed apps → Projecta → Uninstall**. Uninstall removes
the application files, the current user's Start menu shortcut, and its
uninstall registration, but intentionally retains all of
`%LOCALAPPDATA%\Projecta`. Review and remove that data yourself only after
making any needed backup.

For help, report the Windows version and architecture, whether install,
workspace creation, readiness, stop/restart, and uninstall succeeded, plus
any warning or error code. Do not send secrets, DPAPI material, workspace
content, or raw logs.

## Limits

The owner-authorized unsigned exception is limited to the 0.7.0 test
pre-release; ordinary release signing and signed-update verification remain
fail-closed. The package includes `THIRD-PARTY-NOTICES.md` and individual
runtime license files. Its inventory identifies five app-local Microsoft
Visual C++ DLLs:

- `runtime/java/bin/msvcp140.dll`
- `runtime/java/bin/vcruntime140.dll`
- `runtime/java/bin/vcruntime140_1.dll`
- `runtime/python/vcruntime140.dll`
- `runtime/python/vcruntime140_1.dll`

The three Java-directory files are from the Temurin JRE 21.0.12.1+1 archive
and have Microsoft file version 14.40.33810.0; the two Python-directory
files are from the CPython 3.12.10 embeddable archive and have file version
14.42.34438.0. The inventory records valid Microsoft Authenticode signatures;
signature verification was run with revocation checks disabled.

Microsoft's [Visual C++ redistribution terms](https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files?view=msvc-170)
limit redistribution to licensed Visual Studio users and eligible REDIST-list
files. Before distributing this bundle, the owner must confirm these exact
files meet those terms. File-signing evidence does not establish redistribution
rights. The genuine outstanding distribution condition is this specific
REDIST-list eligibility check; this handoff does not require blanket paid-counsel
approval. The developer-host smoke does not prove a clean machine, absence of
development tools, redistribution eligibility, a selected journey, production
readiness, or `1.0.0` approval. The second-machine manual test remains unverified.
