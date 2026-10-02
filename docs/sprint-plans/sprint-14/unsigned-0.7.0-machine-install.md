# Projecta 0.7.0 unsigned test pre-release — Windows 11 x64

This is the owner-authorized unsigned 0.7.0 test pre-release, not a signed
release, production installation, or clean-Windows certification. Windows
cannot verify the publisher; a standard SmartScreen reputation warning may
appear for this unsigned file. A Defender malware alert, Windows hard block,
or organization-policy block is different: stop and report it. Never disable
SmartScreen, Defender, or other security controls, override a malware
detection, or change organization policy. This exception applies only to
0.7.0; signed release and update verification remain fail-closed.

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

The owner-authorized unsigned 0.7.0 hybrid candidate has not been published;
this handoff has no public download URL or published installer checksum. A
local package/archive and unsigned NSIS installer candidate now exist for
review, but they are not a published, publication-approved user download.
The owner's machine-2 QA acceptance is not permission to substitute arbitrary
build files for the eventual exact asset. The previously recorded pre-hybrid
installer and checksum are superseded and must not be run. The eventual asset name is
`Projecta-Setup-0.7.0-win-x64-unsigned-prerelease.exe`, but its final size and
SHA-256 must come from the owner-approved publication, not an older receipt.
Do not substitute a repository checkout, `build` folder, package archive, or
other installer candidate for that exact published asset.

The local S14-08-W20261002-A2-R1 candidate has owner-reported acceptance of
candidate identity, first-run/lifecycle, prerequisite handling, and
uninstall/data retention on machine 2. Separately, the developer-host smoke
exercised its extracted package; it did not execute NSIS on the owner's
existing profile because shell KnownFolder/registry integration was not
safely isolatable there. Do not repeat the accepted owner checks to reconfirm
them. The owner approved unsigned task closure; clean-Windows/resource,
signing, and real missing-runtime vendor execution remain open release gates.
This is not a published download. Use only the exact publication-approved
asset when its filename, size, and SHA-256 are listed here.

When the owner-approved release is available, compare its exact filename,
size, and SHA-256 before opening it. In Command Prompt:

```cmd
certutil -hashfile "%USERPROFILE%\Downloads\Projecta-Setup-0.7.0-win-x64-unsigned-prerelease.exe" SHA256
```

Proceed only if the filename, size, and checksum exactly match the published
asset. If the asset or checksum is unavailable, stop and wait. After those
checks, you may choose **More info → Run anyway** only for an ordinary
SmartScreen unrecognized-app/reputation warning, only if Windows offers that
option, and only if you accept the unsigned 0.7.0 test risk. This is an
optional per-file choice for this verified asset, not a safety check or
permission to run other unsigned files. If Defender reports malware, Windows
hard-blocks the file, or organization policy blocks it, stop and report the
alert; do not override it or change security settings.

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
licensed Visual Studio users and applicable terms. This candidate includes
neither disputed runtime DLLs nor the vendor installer; the user downloads and
accepts Microsoft's package under Microsoft's UI. This is not a blanket waiver
or legal opinion for other third-party contents.

The worker host already had x64 v14 runtime **14.50.35719.0**, above the
minimum, so the real installed-runtime check could exercise only the skip path.
It is not a clean Windows image and does not prove the missing-runtime vendor
installer/UAC branch. The owner-reported GUI baseline above is not a new
first-run test of this installer. This unsigned exception applies only to 0.7.0;
signed update verification remains fail-closed. Clean-Windows dependency
closure, minimum-resource measurements, owner signing configuration, and the
remaining S14 evidence gates are still open.
