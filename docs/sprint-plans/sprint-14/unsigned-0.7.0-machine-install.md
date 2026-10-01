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

The owner-authorized GitHub 0.7.0 release page has not been published. This
handoff has no public download URL. When the owner-approved asset is available,
verify its exact filename and size before opening it:

`Projecta-Setup-0.7.0-win-x64-unsigned-prerelease.exe`

Handoff candidate size: **123,908,108 bytes**.

Handoff candidate SHA-256:

`1c3845f88f93f25f3669706ec2a950dd3ad716c41e5a1efc1a9df3fbb4f63222`

Compare the downloaded file before opening it. In Command Prompt:

```cmd
certutil -hashfile "%USERPROFILE%\Downloads\Projecta-Setup-0.7.0-win-x64-unsigned-prerelease.exe" SHA256
```

Proceed only when the downloaded file came from the owner-approved release
asset and matches the exact filename, size, and SHA-256 above. The public page
is not available yet; if the asset or matching checksum is unavailable, stop
and wait. Do not use a repository clone, a `build` folder, or a copied package
directory. Do not turn off security controls or use a “run anyway” bypass if
SmartScreen or antivirus software blocks the file.

## Install and start

1. Sign in to the Windows 11 x64 account that will use Projecta. This is a
   per-user install and does not need administrator privileges. Do not choose
   **Run as administrator**.
2. Double-click the verified `.exe`. Read the unsigned-test warning and
   continue only after verifying the asset; otherwise cancel.
3. Keep the default `%LOCALAPPDATA%\Programs\Projecta\0.7.0` location and
   finish the wizard. Choose **Open Projecta** on the finish page.
4. On first launch, enter a display name for this local workspace. Wait for
   the panel summary **Ready — all four local services are running** and check
   that PostgreSQL, Fuseki, Semantic Core, and API each show **Running**. The
   default browser opens `http://127.0.0.1:18732/`; use **Open Projecta in
   browser** in the panel if needed.

This handoff smoke covers installer completion, first-run workspace naming,
four-service readiness, and the loopback browser only. It does not claim a
selected product journey, manual review receipt, or capture compatibility.

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

Report the Windows version/architecture, whether installation, readiness,
stop/restart, and uninstall succeeded, and any warning or error code. Do not
send secrets, DPAPI material, workspace content, or raw logs.

## Limits

This unsigned exception is limited to the owner-authorized 0.7.0 test
pre-release. The installed package includes `THIRD-PARTY-NOTICES.md` and the
individual runtime license files. Its inventory records five app-local
Microsoft Visual C++ DLLs sourced from the Temurin and CPython archives.
Microsoft's [Visual C++ redistribution terms](https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files?view=msvc-170)
limit redistribution to licensed Visual Studio users and eligible REDIST-list
files; the owner must confirm that these exact DLLs meet the applicable terms
before distribution. This is a specific licensing prerequisite, not a
blanket paid-counsel gate. The developer-host smoke does not prove a clean
machine, absence of development tools, redistribution eligibility, a selected
journey, production readiness, or `1.0.0` approval. The second-machine manual
test remains unverified.
