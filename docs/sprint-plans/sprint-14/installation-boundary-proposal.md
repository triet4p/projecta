# S14-07 — User installation boundary proposal

**Status: APPROVED — INSTALLATION ARCHITECTURE ONLY (owner decision recorded 2026-09-30).** The owner selected the Windows 11 x64 per-user launcher with bundled native services, rather than the managed-container or hosted routes. This records route selection only; it does not certify the open S14-08 prerequisites, approve production or any release/`1.0.0`, or permit Compose-data migration. See the [decision log entry](../../../.agents/memory/decisions.md#2026-09-30-select-the-windows-11-x64-per-user-launcher-for-local-installation).

## 1. Owner-approved installation decision

Requirement §4 says a user must not have to install and operate Docker; a browser at `localhost` is acceptable. The S14-07 boundary must still preserve the existing Compose-first developer/CI path and the application, API, migration, and semantic contracts. See [Sprint 14 requirements](../sprint-14-requirements.md), [the S14-07/S14-08 plan](../sprint-14.md), and [the approved deployment choice](../../initialization/08-Deployment-Choice.md).

**Owner-selected route:** Windows 11 x64, per-user Projecta launcher with a bundled native local service runtime. The launcher is scoped to manage the current application services as local child processes, then open the existing React SPA in the user's browser at a loopback-only URL. It bundles the runtime dependencies, not Docker or another container engine. This choice preserves the existing Compose developer/integration-test/CI baseline and makes no production deployment decision.

This route intentionally gives up identical OCI image execution on the user's machine. It retains the same API and Semantic Core code, PostgreSQL major version, Fuseki/TDB2 boundary, migrations, ontology/SHACL behavior, service contracts, and readiness semantics. The current deployment decision requires local/production PostgreSQL and Jena major-version parity, not identical host binaries; a native port still needs explicit cross-runtime integration evidence. This selected route amends only the user distribution boundary in the [2026-08-05 web-first decision](../../../.agents/memory/decisions.md), which had deferred bundling the backend topology; the Compose developer/CI baseline remains unchanged.

## 2. What the current repository actually requires

The current browser experience is not a standalone static page. The `compose.yaml` `web` profile starts the React/Nginx web service together with the API, Semantic Core, Fuseki, Fuseki bootstrap, PostgreSQL, and the API migration job. API readiness depends on both PostgreSQL/migrations and Semantic Core; Semantic Core waits for Fuseki bootstrap. The web container exposes the browser entry point. The current service and data contracts are visible in [`compose.yaml`](../../../compose.yaml), [`compose.dev.yaml`](../../../compose.dev.yaml), and [`compose.prod.yaml`](../../../compose.prod.yaml).

| Current boundary | Observed source contract | Consequence for a Docker-free installation |
| --- | --- | --- |
| Application API | Python `>=3.12,<3.13`, FastAPI and locked runtime dependencies; health/readiness checks; API currently expects a server-established context and a secret-store master key in `experience` mode. | Bundle a pinned Python 3.12 x64 runtime and the locked Windows runtime dependencies. The launcher supplies local configuration; users do not install Python or edit `.env`. |
| Semantic Core | Java 21; service artifact and libraries built by Maven; calls Fuseki through the existing API boundary. | Bundle a Java 21 x64 JRE plus the built Semantic Core runtime files. Do not include Maven or a developer JDK. |
| RDF service | Fuseki/Jena 6.2.0 with one persistent TDB2 dataset; bootstrap loads ontology and optional initial project data. TDB2 has one-writer/one-JVM ownership. | Bundle the Windows Fuseki distribution and ontology files; enforce one manager instance and one Fuseki writer. Do not share a live TDB2 directory with Compose or another process. |
| Operational database | `postgres:16.4-alpine` is required by the current web profile and API migrations, even though the selected Notes/capture/review/Graph journeys do not need an external connector. | Bundle a supported Windows x64 PostgreSQL 16 runtime; run the same migrations. Do not substitute SQLite for PostgreSQL or silently omit a current-profile dependency. |
| Other API state | The API also has a persistent operational SQLite file, a filesystem evidence root, and an encrypted interactive LLM secret store. Compose maps these separately from PostgreSQL and Fuseki. | Keep SQLite, evidence, PostgreSQL, TDB2, configuration, secrets, and logs under one versioned per-user data root with separate subdirectories and backup coverage. |
| Web client | The built React SPA uses relative same-origin `/v1` and `/health` URLs (`ProjectaApiClient` defaults to an empty base URL); Nginx currently serves static files and proxies those paths. | Bundle compiled web assets, not Node/npm. The API's directory-backed SPA path is now used by the native package, and the builder runs `npm run build` before staging. A frozen host-validation package and refreshed Notes UI were exercised on the development host; clean-machine readiness remains unestablished. Keep the existing Nginx web service unchanged in Compose. |
| Optional services | Keycloak and OpenBao are opt-in Compose profiles for production identity/secrets, not prerequisites of the local `web` experience. There is no default Redis, search engine, event broker, or object-storage service. | Do not bundle Keycloak, OpenBao, Redis, Kafka/Redpanda, OpenSearch, MinIO, or a production secret manager in this first local-user boundary. This is not a production/multi-user deployment. |
| Optional model integration | Manual composition, exact-span capture, review, and graph inspection work without an LLM. An external provider is entered explicitly in Settings; local Ollama is separately operator-managed and is not started by Projecta. | No model, provider key, Ollama, or runtime network dependency is bundled. The no-provider manual journey is the clean-install proof. |

The local `experience` mode is not authentication. It uses deployment-owned actor/project configuration and a trusted-context secret; startup fails closed when required configuration is absent. The current `.env.example` and `scripts/setup-local-env.ps1` generate local credentials, and the browser must never receive the context secret or provider key. The [local experience runbook](../../runbooks/sprint-7-local-experience.md), [runtime configuration contract](../../architecture/runtime-configuration.md), [API settings](../../../apps/api/src/projecta_api/config.py), and [startup validation](../../../apps/api/src/projecta_api/startup.py) establish those boundaries.

## 3. Realistic routes and tradeoffs

| Route | User experience and boundary | Advantages | Costs / limitations | Assessment |
| --- | --- | --- | --- | --- |
| **A. Per-user launcher + native local services** | Install one signed Projecta package; click Start; launcher supervises bundled PostgreSQL, Fuseki/TDB2, Semantic Core, and API; opens the browser at `127.0.0.1`. No Docker/container engine, WSL2, Python, Java, Node, PostgreSQL, or administrator install. | Meets the direct no-Docker request without a VM; local data stays on the workstation; preserves the canonical React UI and current service protocols. Manual workflows can run without internet or provider credentials after installation. | Highest packaging and recovery work. Windows runtime builds differ from Linux OCI images; a new launcher, first-run configuration, local static serving, signed dependency inventory, and clean shutdown/backup handling are required. Initially Windows x64 only. | **Recommended.** The browser is already an acceptable product surface; do not add a full desktop application solely to avoid Docker. |
| **B. Projecta-managed Podman machine using OCI services** | A launcher provisions and owns Podman plus its Linux VM, then starts the existing service images and opens localhost. Docker itself is absent from the user's machine. | Closest image/runtime parity; less need to package Python/JVM/PostgreSQL as Windows-native binaries. | This still installs and operates a container engine behind the launcher. Podman on Windows uses WSL 2 by default or Hyper-V as an alternative; host features, virtualization, storage, setup/reboot and potentially administrator involvement must be accepted. Compose-provider compatibility for this repository's profiles, health conditions, volumes, and merge tags has not been proven. | Viable only if the owner accepts an app-managed virtualized runtime and S14-08 proves it on a clean supported Windows image. It is not the recommendation because it may reproduce the very setup burden the requirement is meant to remove. |
| **C. Hosted browser service** | User opens an owner-operated HTTPS web site; all backend services and data are hosted. No local backend installation. | Lowest local installation/support burden; one server stack can serve multiple users. | Not a localhost/offline installation. Requires approved production identity, tenancy, hosting, backups, secret custody, security and data-residency boundaries. Current local `experience` mode is not production authentication; this route would move user data off the workstation and exceeds the current local-user baseline. | A separate product/deployment decision, not a shortcut for S14-08. |

A full Tauri/Electron desktop client would add a native shell but not remove the need to package/manage the backend. The existing web-first decision reserves Tauri for a thin client that calls a separately owned API, not for bundling Python, Java, Fuseki, and storage. A CLI-only wrapper would still make ordinary users handle configuration, process status, and recovery at a command prompt. Under Route A the launcher is a small start/stop/status surface; the browser remains the application UI. A diagnostic CLI may be added only if an actual support need justifies it.

## 4. Selected Route A: exact scope and binary/data boundaries

### Platform and audience

- **Proposed first target:** Windows 11 x64, on a Microsoft-supported Windows 11 release. No Windows 10, macOS, Linux, or ARM64 claim in the first package. The exact minimum Windows feature release and RAM/disk minimum must be fixed from clean-machine tests before publishing an installer.
- Per-user installation and one local OS account; no Windows service, system-wide installation, WSL2, Hyper-V, Docker, administrator privileges, or preinstalled language/database runtime. The runtime does not require network access after the signed package is obtained.
- Local single-user experience mode only. Bind the browser/API entry point and every backend listener to loopback; do not expose the web app, API, PostgreSQL, Semantic Core, or Fuseki to the LAN. This is not multi-user authentication or production security. A person with control of the same Windows account remains inside the local trust boundary.
- Install binaries read-only in the per-user application location. Keep mutable user state outside the install directory under `%LOCALAPPDATA%\Projecta\` so upgrades and uninstall cannot overwrite it.

### Packaged binaries and dependencies

| Package item | Proposed boundary |
| --- | --- |
| `Projecta Local` launcher | Signed, self-contained, per-user executable. Owns one process tree/lock, checks ports and disk space, starts/stops children, waits for readiness, shows sanitized diagnostics, and opens the default browser. Closing the launcher performs reverse-order graceful shutdown; it does not leave Windows services or hidden background auto-start behind. |
| API | Same Projecta FastAPI application and API contracts, packaged with a pinned CPython 3.12 x64 embedded runtime and the locked production dependencies/wheels. Include the compiled SPA assets and a local-only static-file mount so the API is the single same-origin entry point. No development/test dependencies, `uv`, source checkout, or user-installed Python. |
| Semantic Core | Existing built Semantic Core JAR and runtime libraries, launched on the bundled x64 Java 21 JRE. No Maven or JDK. |
| Fuseki/TDB2 | Apache Jena/Fuseki 6.2.0 Windows distribution on the same Java 21 JRE, configured for the Projecta dataset and a single writable TDB2 directory. Include only runtime components needed by the user profile, not Jena developer/test CLIs. |
| Operational PostgreSQL | Windows x64 PostgreSQL 16 binaries and a per-install cluster. EDB currently lists a 16.15 Windows x86-64 binary archive; this is a source candidate, not yet a redistribution/legal approval. Compose currently pins 16.4-alpine. The repository's parity rule is same PostgreSQL major; both patch builds must pass the same integration contract before this version pairing is accepted. |
| Ontology/bootstrap | Read-only packaged ontology and a versioned, non-destructive first-run initializer. Bootstrap is not an every-start seed/reset step. Existing `scripts/bootstrap_fuseki.py` issues `PUT` to the ontology graph and to configured project asserted graphs; it must not be reused unchanged against user data. |
| Not bundled | Docker/Desktop, another container engine, WSL2/Hyper-V, Python/Node/JDK toolchains, a browser, Keycloak/OpenBao, external LLM/model, local Ollama, Redis/search/broker/object storage. The user's existing browser is used; Windows 11 supplies a default browser. |

The Python 3.12 embeddable distribution is a credible packaging candidate, but Python's documentation explicitly requires vendoring third-party dependencies rather than using `pip`, and calls out the Microsoft C Runtime prerequisite. The bundle pipeline must include the correct x64 runtime/wheels, runtime notices/licenses, and the required C runtime; this has not yet been built. Fuseki's Windows batch launcher and Java 21 requirement, and a Windows x64 PostgreSQL 16 binary source, are documented by the upstream projects linked below.

### First-run configuration, secrets, and data

- The first-run launcher wizard writes an app-owned configuration file containing a workspace display name, generated valid project ID, fixed local actor identity, runtime versions, and data paths. It seeds only a fresh data directory. The owner approved first-run-only project provisioning; the checked-in `Project Alpha/Beta` acceptance fixture is not presented as customer data.
- Generate unique PostgreSQL credentials, trusted-context secret, and Fernet master key at first run. Store their protected values with Windows DPAPI **CurrentUser** scope, not in `.env`, a browser store, source, or ordinary configuration text. The launcher decrypts only the values needed to start the API/PostgreSQL children and supplies them through the child-process environment. This protects them at rest from other Windows accounts, not from malware/process inspection under the same account or a compromised local process.
- Continue to use the existing server-side encrypted LLM credential store. A user enters an optional provider credential through Settings; the API returns only configured/redacted status. Manual Notes, capture, review, and Graph journeys must remain usable with no provider configured. Do not bundle a provider credential or silently call an external model.
- Keep durable state under `%LOCALAPPDATA%\Projecta\data\`: PostgreSQL cluster, TDB2 dataset, API operational SQLite database, evidence files, and versioned local configuration. Keep sanitized logs and the DPAPI-protected secret blob in separate app-owned locations. The package binds backend ports to loopback; only the browser-facing local origin is meant for user interaction.
- DPAPI CurrentUser means encrypted runtime secrets are tied to that Windows account/device. A machine/account migration must not copy the DPAPI blob as if it were portable. After data recovery on another account/machine, provider credentials must be re-entered; credential/master-key material is excluded from the separately governed S14-09–11 portable-data contract.

### Lifecycle, updates, and recovery

1. One launcher instance acquires the runtime lock and validates platform, free space, data-version compatibility, and loopback ports. A collision or unsupported platform fails visibly; the app must not bind to a LAN address or silently choose a different service endpoint.
2. Start PostgreSQL and Fuseki as parallel dependency branches. Wait for native health checks; then apply forward-only API migrations and run the safe, one-time ontology/project initializer. Start Semantic Core after Fuseki readiness, then API after Semantic Core and PostgreSQL/migration readiness. Open the browser only after API and static UI readiness.
3. Stop in reverse dependency order, request graceful database/JVM/API shutdown, retain all state, and release the lock. Browser-tab closure alone does not imply that state should be reset; the launcher exposes an explicit Stop/Exit action. No automatic retry loop, default-project substitution, or “healthy” empty response after a failed dependency.
4. Updates are **user-initiated and signed**, with no silent background service/image/runtime pulls. A release package contains all pinned binaries and notices; the user sees its version and accepts installation. Before an incompatible data migration, stop services cleanly and make a quiesced snapshot of PostgreSQL, TDB2, SQLite, evidence, and local configuration. Apply forward migration only after that checkpoint; do not downgrade schemas. If migration/readiness fails, keep the app stopped, preserve both the failed data and prior snapshot, report the failed service/stage, and use a tested restore procedure. Uninstall preserves user data by default; destructive purge requires a separate explicit confirmation.
5. The snapshot is a local recovery mechanism, **not** the portable project export. Do not mount, rewrite, or automatically migrate existing Compose volumes into native Windows data directories. Cross-machine or Compose-to-user migration remains closed until the separately approved S14-09–11 export/import contract exists. Existing developer `.env` secrets must never be imported into the user installation.

For failed startup, identify the service/dependency, readiness code, safe log location, and one recovery action without exposing secret values or source content. Port-in-use, missing/corrupt state, disk-full, invalid configuration, failed migration, Fuseki/TDB2 lock, or lost DPAPI keys are errors, not a blank-success experience. Never delete local data to make readiness pass. A lost provider credential is reconfigured; a damaged data directory is recovered only from a verified snapshot/export.

## 5. Clean-install, Docker-absent proof plan for S14-08/S14-12

Use a disposable clean Windows 11 x64 VM or equivalent resettable image. Record the exact OS release, architecture, account privilege, package hash/signature, and available CPU/RAM/disk before the run. It must have no Docker Desktop, Docker CLI/daemon, Python, Node, Java, or PostgreSQL preinstalled. Install using a standard user account with no elevation; disconnect networking after obtaining the signed installer so the runtime cannot rely on image/package pulls, an external provider, or a hosted service.

Retain the pre-install output of these PowerShell checks, and inspect the installed-app inventory for Docker Desktop; a missing command alone does not prove that no daemon/runtime is installed:

```powershell
Get-Command docker, python, node, java, psql -ErrorAction SilentlyContinue
Get-Service -Name '*docker*' -ErrorAction SilentlyContinue
```

These checks were planned for the former full S14-08 gate, not run for
S14-07. The owner's later unsigned task-closure decision keeps them open for
the separate clean-Windows release gate and S14-12; they are not passed proof.

1. Verify `docker.exe`, Docker Desktop, and Docker services are absent before install and remain absent after launch. Also verify that the launcher did not install WSL2, Hyper-V, or another container runtime.
2. Install and start from the user's shortcut. Observe the launcher service states and readiness chain, then open only the displayed `http://127.0.0.1:<port>` origin. Verify that backend listeners are loopback-only and that a port collision, invalid state, or unhealthy dependency is shown as a failure without deleting data or claiming readiness.
3. With no LLM/provider configured and network disconnected, complete the source-backed exact-span capture and manual review Journey 1 in [the Sprint 14 journey plan](./user-journeys.md). Use the supported disposable first-run project fixture, verify an explicit review receipt, and confirm there is no provider call or silent graph materialization. S14-12 can then run Journeys 1–3 and cross-project checks on the approved installation; S14-13 remains a direct owner/target-user gate, not an agent test.
4. Stop and relaunch using the launcher. Verify the project, note, candidate/review receipt, evidence, and graph state persist. Exercise a controlled failed dependency/startup and confirm a diagnostic and safe recovery path. Exercise upgrade/rollback only after the full state snapshot/restore and migration path is implemented.
5. Separately run the canonical Compose developer/CI validation and parity suites under the existing Compose configuration. This is not evidence that the package works without Docker; the clean-VM browser run is the no-Docker proof.

This clean-machine, Docker-absent proof remains open. The corrected unsigned host-validation archive (SHA-256 `a6e6519ba279d8fe4dd3162108abf87c6b360888ae6a8c17524c5b9411db369b`) was staged with isolated `LOCALAPPDATA` on the development Windows 11 Home Single Language x64 build 26200 host. All four services reached ready; the API health endpoint returned HTTP 200, and the browser loaded the first-run project workspace, Notes exact-span entry point and empty LLM settings. The browser smoke used only the loopback origin. Previously accepted Journey 1 and recovery evidence remains in the task artifact; this smoke did not repeat that journey. It is not resettable standard-user, Docker-absent, offline clean-install, or release proof.

## 6. Feasibility evidence, blockers, and owner approval

Source-based feasibility is credible but incomplete: Apache Jena documents the standalone Windows `fuseki-server.bat` route and Java 21+, EDB lists a Windows x86-64 PostgreSQL 16 binary archive, and CPython documents an embeddable package specifically for application redistribution. Windows DPAPI provides a current-user protection boundary. These sources prove those individual runtime mechanisms exist; they do **not** prove that Projecta's packaged services start together, that the proposed binaries may be redistributed under the intended channel, or that the clean-install journey passes.

The following findings originated under the former full S14-08 gate; after
the owner's unsigned task-closure decision, their unresolved clean/resource,
signing, and real missing-runtime portions remain release prerequisites:

- The owner selected the Windows 11 x64, one-local-OS-user, loopback, per-user boundary. The measured development host was Microsoft Windows 11 Home Single Language, x64, version `10.0.26200` / build `26200`, 8 logical processors and 15.74 GiB visible RAM. F: had 45.82 GiB free before and 45.59 GiB after the corrected-package smoke. This was not a resettable standard-user/Docker-absent image, so resource suitability and clean-host behavior remain unestablished.
- Official source checks identified candidates, not a redistributable release: [CPython 3.12.10](https://www.python.org/downloads/release/python-31210/)
  publishes its x64 embeddable ZIP with Sigstore/GPG signature links and MD5
  `fe8ef205f2e9c3ba44d0cf9954e1abd3`; [Temurin JRE 21.0.12.1+1 metadata](https://api.adoptium.net/v3/assets/latest/21/hotspot?architecture=x64&image_type=jre&os=windows&vendor=eclipse)
  publishes ZIP SHA-256 `d35f31e712f0fcf6ac5a093edc90204fbff22f720ba3950bd09d331d5e621636`; [Fuseki 6.2.0](https://archive.apache.org/dist/jena/binaries/apache-jena-fuseki-6.2.0.zip.sha512)
  publishes SHA-512
  `46e5d798faf80fe5f4b32318750071b9172315f9d86bb3aa3ba4d5e94abe2e21cd194eab349d491a203c934c6e59b370a671b338f2a413110e859dc628ffe934`.
  EDB's [16.15 Windows x64 binaries ZIP](https://get.enterprisedb.com/postgresql/postgresql-16.15-4-windows-x64-binaries.zip) has no publisher SHA-256 found.
  Microsoft's [VC++ v14 redistributable](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist?view=msvc-170) is a moving version permalink; redistribution is limited to licensed Visual Studio users.
- Runtime inputs were fetched and assembled into the earlier unsigned host-validation archive. The corrected inventory resolves 111 exact Maven runtime JARs with published POM/parent metadata and full license texts; completeness does not constitute owner/counsel redistribution approval. Source verification of five app-local Microsoft VC runtime DLLs succeeded, but no separate redistributable installer is included and clean-host dependency proof remains open.
- Implemented Windows 11 gating, per-user locking, loopback child-service configuration, readiness/status/stop handling, migrations, DPAPI CurrentUser secrets, and hash-verified backup/restore with rollback. The previously accepted focused 16-test launcher/API run and nine Maven readiness/configuration tests remain recorded; the new four-second Semantic Core/API probe deadline tests passed separately (2 targeted tests).
- The corrected builder produced `build/native-package-s14-08-final` and `build/ProjectaLocal-0.6.0-win-x64-S14-08-HOST-VALIDATION-UNSIGNED-FINAL.zip` (183,341,207 bytes; SHA-256 `a6e6519ba279d8fe4dd3162108abf87c6b360888ae6a8c17524c5b9411db369b`). The ZIP CRC passed; all 6,338 manifest-listed payload-file hashes/sizes and all 330 indexed notice paths were verified. The manifest remains `releaseEligible=false`, with no update signature, public-key fingerprint, or Authenticode metadata.
- PostgreSQL parity — a fresh isolated Compose 16.4-alpine database and scratch native EDB 16.15 database both migrated to `0011_review_receipts_append_only`; the same connector and append-only receipt integration files passed 4 tests on each. The temporary databases were stopped and removed. This does not replace the separate clean Windows 11 proof.
- The post-correction frozen runtime reached `/health/ready` HTTP 200 with `{"status":"ready","semanticCore":"ready","oidc":"ready"}` 61,795 ms after start. Launcher status showed PostgreSQL, Fuseki, Semantic Core, and API running, with listeners on `127.0.0.1:15432`, `:18303`, `:18080`, and `:18732`. The package contains the corrected four-second outer Semantic Core/API probe deadlines around the nested three-second checks; their delayed-success and single-request timeout regressions passed in the focused suite.
- Runtime inspection covered 345 x64 PE images with zero unresolved static/delay imports and 95 dynamic-string candidate occurrences across 30 names. During launcher, database, Java, Python/API, readiness, and browser operations, only `shcore.dll` matched a candidate in loaded modules; it resolved to `C:\WINDOWS\System32\SHCORE.dll`. The other 29 distinct names were not observed in this run and remain unverified code paths, not proven missing imports. Java loaded VC runtime DLLs from `runtime/java/bin`; PostgreSQL loaded `VCRUNTIME140.dll` and `VCRUNTIME140_1.dll` from the frozen launcher's PyInstaller temp extraction; the API loaded extensions from packaged `runtime/python`. This host observation does not prove clean-OS dependency closure.
- At readiness, 11 package processes used 664.98 MiB aggregate working set and 620.89 MiB aggregate private bytes over four one-second samples. Archive, unpacked package, and isolated data sizes were 183,341,207, 403,862,141, and 251,603,235 bytes respectively. Resource suitability against a published minimum remains open.
- Open gates remain: resettable Windows 11 standard-user proof with Docker/container runtimes absent; clean-host dependency proof; the four owner Ed25519/Authenticode signing settings and valid owner certificate/timestamp path; and owner/counsel redistribution approval. No release or distribution approval is claimed.

### Later hybrid-installer clarification (2026-10-01)

The five-file Visual C++ DLL inventory and redistribution finding above describe
the earlier bundled-file candidate, not the owner-approved hybrid 0.7.0
candidate. The hybrid package removes versioned MSVC runtime DLLs from staged
files and both PyInstaller archives, bundles no Microsoft Redistributable
installer, and downloads the prerequisite directly from Microsoft only when
the user's x64 runtime is missing or below the build-derived minimum. The
Microsoft installer retains its own terms/consent UI and may request UAC;
Projecta and its services remain per-user. This supersedes only that specific
five-DLL condition. It does not waive other bundled-component terms or the
clean-Windows, signing, and remaining S14 evidence gates. See the latest
candidate identity and scoped verification in
`artifacts/sprint-14/task-08.md`; no artifact is published here.

### Current local hybrid candidate evidence (2026-10-02)

The fresh attempt-specific S14-08-W20261002-A2-R1 package directory and ZIP
were built locally. The ZIP is 197,401,370 bytes with SHA-256
`b5dcb57447c61b6b482e0c3634c92c799bb22a1d79a362b13a4f80ce19637fa5`. Its
embedded `runtime/source-provenance.json` is SHA-256
`e1dfadbebde7c4eae55b2156576da13a7bb9df804fcbd8546f4f471cc6c99bd3`, records
base revision `c724ac5f3c66d7d1cb46267fadb31c35955bb825` separately from 282
selected build-input files, and binds 17 derived-output groups. The source-file
digest is
`05d902983fe6e284f078802b3972bdce85105ea4c800fba5941bd33391679843`. The
independently checked package tree contained 6,133 manifest payloads; its ZIP
contains those files plus the root manifest, passed CRC verification, and
includes all 332 indexed notices. The NSIS installer is 122,399,569 bytes,
SHA-256
`fbcc802be3063fb3aa1fe81376fa916599f87de9a0da50658b1691f0cfbefb85`, and
Authenticode `NotSigned`. The installer receipt binds the package provenance,
installer source scripts, NSIS 3.13 archive/compiler, and license notice. Both
candidate receipts say `releaseEligible=false`; no artifact is published.

On the existing developer host only, the extracted R1 package was run with
isolated local profile/data paths. Its bundled services reached ready; the
browser captured a selected exact source span and recorded accepted manual
receipt `df2dabd37704ccd4fe0c24e188c24d57fc557673b396fb6000eb1c7a11676eac`
without a model/provider or assertion materialization. The receipt and source
anchor persisted across stop/restart. A fixed-port collision failed with
`PORT_IN_USE` without starting services or changing the isolated workspace.
The native inventory has zero unresolved imports across 340 PE images; only
`SHCORE.dll` among 30 dynamic-candidate names was observed in this runtime,
loaded from the Windows System32 directory. Other dynamic-string names remain
unobserved, not proven missing.

The worker-host compiled NSIS installer was not executed. Its fixed `%LOCALAPPDATA%`
installation path, Start Menu shell KnownFolder shortcut operations, and HKCU
uninstall registration cannot be safely isolated on this host: `.NET`
`Environment.GetFolderPath("Programs")` continued to resolve to the owner
Start Menu after process `APPDATA`/`LOCALAPPDATA` overrides, and the existing
owner installation/workspace are present. Clean Windows installation,
missing-runtime vendor consent/UAC, and owner-held signing remain unverified.
The owner subsequently confirmed all four machine-2 QA checks and explicitly
approved unsigned S14-08 task closure after fresh review and the checkpoint.
This candidate remains unpublished; clean-Windows/resource-floor, signing,
and real missing-runtime vendor proof remain separate open release gates.


### Selected route and alternatives

1. **Selected — per-user native launcher:** Windows 11 x64 first; signed per-user launcher; bundled native Python/API, Java/Semantic Core, Fuseki/TDB2, and PostgreSQL runtime; loopback browser; one local OS user; no Docker, WSL2/Hyper-V, administrator installation, or preinstalled language/database runtimes; optional provider; fresh local data only; manual user-approved updates with tested backups; existing Compose unchanged for developer/CI.
2. **Not selected — managed-container route:** Projecta would install/manage Podman plus its Windows WSL2/Hyper-V machine and start OCI services; this requires accepting its virtualization/admin/reboot and storage prerequisites and a clean Windows/Docker-absent Compose-compatibility proof.
3. **Not selected — hosted web:** defer local packaging and approve a separate hosted-service, identity, tenancy, secret, data-location, and operations design. This does not satisfy a local/offline user path.

**Owner decision (2026-09-30): approved the Windows 11 x64 per-user native launcher route.** The selected boundary is one local OS user, bundled native API/Semantic Core/Fuseki-TDB2/PostgreSQL services, and the same-origin SPA at a loopback browser origin; Docker, WSL2/Hyper-V, administrator installation, and user-installed runtimes are outside the selected route. Preserve the Compose developer/CI baseline and do not automatically migrate Compose data. This is installation-architecture approval only; exact runtime binaries/signatures/redistribution, platform/resource measurements, DPAPI secret implementation, non-destructive Fuseki bootstrap, lifecycle/backup/recovery, and clean no-Docker proof remain S14-08 implementation/verification requirements. It is not production, exact-binary/license, release, or `1.0.0` approval. S14-07 remains [~] pending Main's evidence review. See the [decision log entry](../../../.agents/memory/decisions.md#2026-09-30-select-the-windows-11-x64-per-user-launcher-for-local-installation).

## Sources

### Repository evidence

- [Sprint 14 plan](../sprint-14.md), [requirement §4](../sprint-14-requirements.md), and [user journeys](./user-journeys.md).
- [Deployment choice](../../initialization/08-Deployment-Choice.md) §§3, 5, 7, 9, 10, and 11; [decision log](../../../.agents/memory/decisions.md).
- [Compose topology](../../../compose.yaml), [development overlay](../../../compose.dev.yaml), [environment template](../../../.env.example), [setup script](../../../scripts/setup-local-env.ps1), and [README current Docker quickstart](../../../README.md).
- [API dependency/image contracts](../../../apps/api/pyproject.toml), [API runtime settings](../../../apps/api/src/projecta_api/config.py), [readiness requirements](../../../apps/api/src/projecta_api/startup.py), [Semantic Core Java version](../../../services/semantic-core/pom.xml), [Fuseki image versions](../../../infra/docker/fuseki/Dockerfile), [SPA same-origin client](../../../apps/web/src/api/client.ts), and [Fuseki initializer](../../../scripts/bootstrap_fuseki.py).

### Upstream platform evidence

- Apache Jena: [Fuseki quickstart](https://jena.apache.org/documentation/fuseki2/fuseki-quick-start.html), [Fuseki server on Windows](https://jena.apache.org/documentation/fuseki2/fuseki-server.html), and [Jena downloads/system requirements](https://jena.apache.org/download/).
- PostgreSQL/EDB: [official Windows download route](https://www.postgresql.org/download/windows/) and [EDB PostgreSQL binary archives](https://www.enterprisedb.com/download-postgresql-binaries) (the current result lists PostgreSQL 16.15 Windows x86-64 binaries).
- Python: [Python 3.12 Windows embeddable package](https://docs.python.org/3.12/using/windows.html#the-embeddable-package) (vendor third-party dependencies; no pip; include Microsoft C Runtime as required).
- Windows secrets: Microsoft [CryptProtectData / DPAPI](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata) (default protection is current-user scoped).
- Managed-container alternative: [Podman installation](https://podman.io/docs/installation) and [Hyper-V preparation/admin requirements](https://docs.podman.io/en/latest/markdown/podman-system-hyperv-prep.1.html).
