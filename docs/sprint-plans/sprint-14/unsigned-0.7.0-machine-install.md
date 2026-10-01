# Projecta 0.7.0 unsigned test pre-release — Windows 11 x64

This is the owner-authorized unsigned 0.7.0 test pre-release, not a signed
release, production installation, or clean-Windows certification. Windows
cannot verify the publisher; a standard SmartScreen reputation warning may
appear for this unsigned file. A Defender malware alert, Windows hard block,
or organization-policy block is different: stop and report it. Never disable
SmartScreen, Defender, or other security controls, override a malware
detection, or change organization policy. This exception applies only to
0.7.0; signed release and update verification remain fail-closed.

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
and wait. After those checks, you may choose **More info → Run anyway** only
for an ordinary SmartScreen unrecognized-app/reputation warning, only if
Windows offers that option, and only if you accept the unsigned 0.7.0 test
risk. This is an optional per-file choice for this verified asset, not a
safety check or permission to run other unsigned files. If Defender reports
malware, Windows hard-blocks the file, or organization policy blocks it, stop
and report the alert; do not override it or change security settings.

## Install and start

1. Sign in to the Windows 11 x64 account that will use Projecta. This is a
   per-user install and does not need administrator privileges. Do not choose
   **Run as administrator**.
2. Double-click the verified `.exe`. For only the ordinary SmartScreen warning
   described above, use **More info → Run anyway** if offered and if you accept
   the risk; otherwise cancel. For a malware alert, hard block, or policy
   block, stop and report it.
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
files are from the [CPython 3.12.10 Windows embeddable archive](https://www.python.org/downloads/release/python-31210/)
and have file version 14.42.34438.0. The package receipt and runtime manifest
identify the bundled Python runtime as 3.12.10; Python 3.12.12 was used to
freeze the separate desktop GUI, not as the source of these bundled DLLs.
The inventory records valid Microsoft Authenticode signatures; signature
verification was run with revocation checks disabled.

Microsoft's [Visual C++ redistribution guidance](https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files?view=msvc-170)
says distribution of Visual C++ Runtime Redistributable packages and
individual binaries is limited to licensed Visual Studio users and subject
to Microsoft's Software License Terms. The [Visual Studio 2022 REDIST
list](https://learn.microsoft.com/en-us/visualstudio/releases/2022/redistribution)
allows only its listed, unmodified distributable code under that edition's
terms; other Visual Studio editions/versions have their own applicable lists.
Before public binary distribution, the owner must verify that each of the five
files above is eligible under the applicable Visual Studio edition/version's
REDIST list and license terms. Their Temurin/CPython origins and Microsoft
signatures do not establish redistribution rights; using Visual Studio Code
alone does not establish a licensed Visual Studio entitlement. No blanket
paid-counsel approval is asserted here. The specific outstanding condition is
owner confirmation of eligibility for these five app-local DLLs. The
developer-host smoke does not prove a clean machine, absence of development
tools, redistribution eligibility, a selected journey, production readiness,
or `1.0.0` approval. The second-machine manual test remains unverified.
