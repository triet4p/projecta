# Projecta 0.7.0 unsigned release — Windows 11 x64

The published, owner-authorized v0.7.0 package is unsigned and intended for
Windows 11 x64 only. It does not contain the subsequent connector
Enable/Disable 503 fix; wait for the separate verified v0.7.1 release if that
correction is required. This package is not signed, production-certified, or
clean-Windows certified. Windows cannot verify its publisher; a standard
SmartScreen reputation warning may appear. A Defender alert, hard block, or
organization-policy block is different: stop and report it. Never disable
security controls. Signed release and update verification remain fail-closed.

The bundle includes the local Python 3.12 and Java 21 runtimes, PostgreSQL,
Fuseki/TDB2, Semantic Core, API, and web assets. It does not bundle the
Microsoft Visual C++ runtime DLLs or its Redistributable installer. Before
Projecta can open, it checks for the pinned x64 Visual C++ v14 runtime. If
that version or a newer compatible version is already registered, setup skips
the prerequisite. Otherwise Internet access is required to download the
official installer directly from Microsoft after your consent; Microsoft's
own license/consent UI and a Windows UAC prompt may appear. Only that vendor
prerequisite can be elevated; Projecta and its services remain per-user. You
do not need Docker, Python, Node.js, a JDK, PostgreSQL, or Fuseki installed
separately. The browser is not bundled; Projecta opens the current Windows
account's default browser.

## Get and verify the installer

The published v0.7.0 release is Latest at
<https://github.com/triet4p/projecta/releases/tag/v0.7.0>. Use only its exact
installer asset:

`Projecta-Setup-0.7.0.exe` (122,493,613 bytes; SHA-256
`91209858aabc2e15695e7752c021d4bf34a348705a8ad475ac31b48bf0979cf4`).
The release also publishes `SHA256SUMS-0.7.0.txt`; verify the installer
against that file before running it.

The earlier attempt-named installer and pre-hybrid checksum are not the public
asset. Do not substitute a repository checkout, `build` folder, package
archive, or another installer candidate. The public 0.7.0 binary was built
from tag `v0.7.0` at source
`09ea7d05c37db74159a822fc059b7f363e11d41b` and predates the later connector
Enable/Disable 503 fix.

The owner's machine-2 QA acceptance and developer-host smoke describe historic
0.7.0 evidence; they do not certify a clean Windows host, the missing-runtime
Microsoft installer/UAC branch, or the later 0.7.1 package. The upcoming 0.7.1
candidate is not built or published at this source cutover. Do not use a local
0.7.1 build output as a release asset.

Only obtain 0.7.0 from the public release above, and compare its filename,
size, and checksum before opening it.

Before opening the published 0.7.0 asset, compare its exact filename, size,
and SHA-256 with the release listing above. In Command Prompt:

```cmd
certutil -hashfile "%USERPROFILE%\Downloads\Projecta-Setup-0.7.0.exe" SHA256
```

Proceed only if the filename, size, and checksum exactly match the published
release asset. If any does not match, or the checksum is unavailable, stop.
After the checks, you may choose **More info → Run anyway** only for an
ordinary SmartScreen reputation warning, only if Windows offers that option
and you accept the unsigned 0.7.0 release risk. This is an optional
per-file decision, not a safety check or permission to run other unsigned
files. If Defender reports malware, Windows hard-blocks the file, or
organization policy blocks it, stop and report the alert; do not override it
or change security settings.

## Install and start

1. Sign in to the Windows 11 x64 account that will use Projecta. Projecta
   installs and runs per-user. Do not choose **Run as administrator**.
2. Double-click the verified `.exe`. For only the ordinary SmartScreen warning
   described above, use **More info → Run anyway** if offered and if you accept
   the risk; otherwise cancel. For a malware alert, hard block, or policy
   block, stop and report it.
3. Keep the default `%LOCALAPPDATA%\Programs\Projecta\0.7.0` location. Setup
   checks the system's registered x64 Visual C++ v14 runtime before replacing
   application files. If the pinned version or a newer compatible version is
   installed, no download or UAC request is needed. Otherwise setup asks
   whether to download `VC_redist.x64.exe` directly from the official Microsoft
   URL. Choose **Yes** only if you accept this prerequisite; Internet access
   is required. Microsoft displays its own license/consent UI. If installation
   needs elevation, approve the Microsoft installer through Windows UAC; only
   that vendor prerequisite is elevated, never Projecta or its services.
4. If you decline, cancel the Microsoft installer, lack Internet access, or
   verification/installation fails, Projecta will not start and setup will
   leave an existing installation and workspace data unchanged. If Microsoft
   returns a restart-required result, restart Windows yourself and run setup
   again; setup does not reboot Windows automatically.
5. After the prerequisite check succeeds, finish setup and choose
   **Open Projecta**. In the **Create your workspace** dialog, enter a display
   name of 1–128 characters and choose **OK**. Wait for **Ready — all four
   local services are running** and confirm PostgreSQL, Fuseki, Semantic Core,
   and API each show **Running**. The default browser opens
   `http://127.0.0.1:18732/`; use **Open Projecta in browser** in the panel if
   needed.

The owner reported: “Đã mở được, luồng start, mở browser, stop, running đều
đúng. Confimed and continue.” This is user-reported baseline evidence that the
earlier Start/Running/browser/Stop lifecycle worked. It supersedes the earlier
invisible-window symptom only as that reported baseline; it does not establish
the new installer's first-run or missing-runtime flow, identify its cause, or
prove a clean Windows host. No source fix or root cause is inferred.

Later, open **Projecta** from the current user's Start menu to launch the
desktop control panel. Use **Start Projecta** to start the local runtime and
**Open Projecta in browser** to reopen the loopback page. The panel shows
overall readiness plus per-service status. To stop cleanly, choose **Stop
services** and wait until all four service rows show **Stopped**. If the panel
asks whether to keep services running, choose **No** to return to the panel
and stop them first; choose **Yes** only when background operation is
intentional.

## Optional connector administration on corrected 0.7.1 only

This opt-in applies only to a 0.7.1 package rebuilt from source containing the
native environment-forwarding correction and verified after that rebuild. It
does not apply to this historical 0.7.0 installer or to the earlier 0.7.1
candidate, which predates the correction. No 0.7.1 download link is available
in this guide.

Local connector administration is disabled by default. To opt in for the
single-user local experience, stop any running Projecta services, set the
variable in PowerShell, and start the installed manager from that same
PowerShell process:

```powershell
$env:PROJECTA_CONNECTOR_LOCAL_ADMIN_ENABLED = "true"
& "$env:LOCALAPPDATA\Programs\Projecta\0.7.1\ProjectaLocal.exe" start
```

Leave the PowerShell window open while the manager runs. To stop it from a
second PowerShell window, run:

```powershell
& "$env:LOCALAPPDATA\Programs\Projecta\0.7.1\ProjectaLocal.exe" stop
```

After stopping, remove the variable before starting again to retain the
default read-only connector authority:

```powershell
Remove-Item Env:PROJECTA_CONNECTOR_LOCAL_ADMIN_ENABLED -ErrorAction SilentlyContinue
& "$env:LOCALAPPDATA\Programs\Projecta\0.7.1\ProjectaLocal.exe" start
```

The variable is an explicit local experience opt-in, not a production identity
or production authorization mechanism. The API retains its `False` default and
rejects this local-admin setting in production mode.


## Transfer a project between local installations

Projecta's Projects screen can export a project as a `.projecta` package and
import it on another local installation. Transfer the file yourself using a
channel you trust; Projecta does not synchronize the two installations.

1. On the source installation, open **Projects**, export the intended project,
   and save the `.projecta` file. The package excludes provider credentials,
   authentication sessions, and other secret material.
2. Move that file to the destination computer. The package is not encrypted:
   it may contain sensitive project content. Only transfer it when authorized,
   and protect it like the source data.
3. On the destination, open **Projects → Import a project package**, choose
   the file, select **Review package**, and check the project identity,
   contents, and destination before confirming. The SHA-256 value detects
   accidental archive changes; it does not authenticate the sender.
4. Confirm only if the destination is correct and you are authorized to import
   the package. Projecta prepares a private staged copy while its local
   services are stopped, then publishes the catalog last. Existing destination
   project data is never overwritten. A destination conflict stops the import
   without changing the live workspace.
5. Keep the Projects tab open until it reports **Project import complete** or a
   failure code. The imported project appears in the list only after the full
   staged state is published. Projecta does not select it automatically;
   refresh the list if needed, then choose it explicitly. If the import fails,
   the staged copy is discarded or rolled back and the existing destination
   state is retained; report the displayed failure code.

This is a manual, same-contract transfer. It does not establish account sync,
provider credential transfer, clean-host certification, or release readiness.

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

The package includes `THIRD-PARTY-NOTICES.md` and individual runtime license
files, but contains no versioned Microsoft Visual C++ runtime DLLs in its staged
tree or either frozen PyInstaller archive, and no Microsoft Redistributable
installer is bundled or mirrored. Its build-derived x64 v14 minimum is
**14.42.34438.0**. Setup checks the 64-bit installed runtime registry record;
an equal or newer compatible version skips the prerequisite.

If the runtime is absent or older, the bootstrap first explains that Internet
access is required and asks the user before downloading Microsoft's installer
from <https://aka.ms/vc14/vc_redist.x64.exe>. It requires an HTTPS redirect that
stays on a Microsoft host, a valid Microsoft Authenticode signature, Microsoft
publisher identity, x64 Redistributable product metadata, and a file version at
least the package minimum. It hashes the downloaded file around signature and
metadata inspection and recomputes SHA-256 immediately before execution. That
computed hash is an integrity/recheck value, not a Microsoft-published checksum;
Authenticode verification remains the publisher-trust check.

Only Microsoft's own installer is launched with its vendor UI/terms and
`/install /norestart`; UAC may appear for that prerequisite. Projecta and its
services remain per-user and are never elevated. The application will not start
after download/verification failure, user cancellation, installation failure,
or a restart-required result; Windows is never restarted automatically.
The NSIS installer and its supported Start-menu/Finish launch paths use this
PowerShell guard before starting the frozen GUI or Python runtime. Directly
launching `Projecta.exe` bypasses that guard and is unsupported when the
prerequisite is missing.

Microsoft's [latest supported Visual C++ Redistributable guidance](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist?view=msvc-170)
publishes the current x64 download and version guidance. Its
[redistribution guidance](https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files?view=msvc-170)
limits redistribution of its packages and individual files to eligible
licensed Visual Studio users and applicable terms. The published 0.7.0 package includes
neither disputed runtime DLLs nor the vendor installer; the user downloads and
accepts Microsoft's package under Microsoft's UI. This is not a blanket waiver
or legal opinion for other third-party contents.

The worker host already had x64 v14 runtime **14.50.35719.0**, above the
minimum, so the real installed-runtime check could exercise only the skip path.
This was not a clean Windows image and does not prove the missing-runtime vendor
installer/UAC branch; the owner-reported GUI baseline does not establish it
either. This unsigned exception applies only to the v0.7.0 package; signed
update verification remains fail-closed. Clean-Windows dependency closure,
minimum-resource measurements, owner signing configuration, and the 0.7.1
patch binary/publication gates remain separate and open.
