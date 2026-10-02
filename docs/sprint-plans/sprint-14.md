# Sprint 14 Plan — End-to-end Experience and Portable Delivery

Status: `IN_PROGRESS`

Source of requirements: [Sprint 14 requirements and post-sprint release target](sprint-14-requirements.md). This sprint addresses the five recorded requirements; `1.0.0` is a **post-Sprint-14 release target**, not an automatic outcome of completing these tasks.

## Sprint Goal

Make existing Projecta capabilities usable as understandable end-to-end journeys, accessible through a reliable user-facing deployment without requiring the user to install/operate Docker, and portable through a safe export/import handoff between installations. Keep the existing semantic, project-isolation, evidence and review boundaries intact.

## Atomic Tasks

Status legend: [ ] pending / [~] in progress / [x] done.

- [x] **S14-01 — Define user journeys and acceptance scenarios (requirements
  §§1, 3):** Map representative use cases from entry point to usable result,
  including screen purpose, primary action, transitions, states and failure
  paths. Select observable end-to-end scenarios for implementation and user
  trial; do not invent standalone features solely to fill a screen. See the [journey map and trial scenarios](sprint-14/user-journeys.md).
- [x] **S14-02 — Clarify project navigation (requirement §2):** Separate
  choosing/changing a project from navigation within its workspace. Verify
  users know which project is active and the context never silently changes.
- [x] **S14-03 — Integrate session chrome (requirement §2):** Redesign the
  isolated signed-in/sign-out row. Verify session status and sign-out remain
  discoverable without taking an otherwise empty full-width row.
- [x] **S14-04 — Make the Notes capture path understandable (requirements
  §§2, 3):** Expose when to use Note Composer, assisted import and exact-span
  capture and make the capture action discoverable in the in-screen journey.
  Verify users can finish capture and identify the next review step.
- [x] **S14-05 — Connect cross-screen journeys (requirement §3):** Implement
  transitions and state/next-action cues across screens selected in S14-01,
  including return and error paths. Exercise each journey through the real
  UI/backend; retain source-bound review rather than hidden graph writes.
- [x] **S14-06 — Make the graph legible (requirement §2):** Correct node
  text/background contrast and status differentiation across relevant themes
  and interactive states. Verify labels, relationships and legend on real graph
  data are distinguishable without relying on color alone.
- [x] **S14-07 — Decide the user installation boundary (requirement §4):**
    Record the owner's selected Windows 11 x64 per-user launcher with bundled
    native services and a loopback browser entry point for one local OS user;
    preserve the Compose developer/CI baseline and do not automatically migrate
    Compose data. Keep exact runtime/binary licensing, platform/resource
    measurements, DPAPI-backed secret handling, non-destructive Fuseki bootstrap,
    lifecycle/backup/recovery, and clean no-Docker proof as S14-08
    implementation/verification requirements. This approves installation
    architecture only, not production or any release/`1.0.0` decision.
- [~] **S14-08 — Deliver the approved Docker-free user path (requirement §4):**
  Package the owner-approved unsigned 0.7.0 Windows 11 x64 per-user native
  install/start/stop path, with truthful readiness/failure feedback and
  verified source/payload integrity. Accept the frozen-runtime journey proof
  and the owner's four machine-2 QA checks for candidate identity,
  first-run/lifecycle, prerequisite handling, and uninstall/data retention;
  preserve Compose for development/CI. The owner explicitly approved this
  task-closure scope. Clean-Windows/resource-floor, signing, and unreported
  real missing-VC vendor proof remain separate release gates below, not
  completed acceptance claims.
- [ ] **S14-09 — Decide the portable-data contract (requirement §5):**
  Inventory authoritative project, source/evidence, receipt, operational and
  semantic states needed for a usable transfer; define versioned format,
  integrity, ownership, sensitive-data exclusions, compatibility and conflict
  policy. Obtain approval before implementation. Google Drive is manual file
  transport, not a required connector.
- [ ] **S14-10 — Implement project data export (requirement §5):** Produce a
  bounded package from a consistent project snapshot under the approved
  contract, preserving required evidence/provenance and refusing incomplete
  or unauthorized exports. Exclude credentials, master keys and sessions.
- [ ] **S14-11 — Implement manual data import (requirement §5):** Validate the
  package and authorized destination before applying changes, handle conflicts
  and unsupported versions per contract, and restore authoritative state
  without cross-project leakage or implicit approval/materialization. Fail
  safely on tampered or partial input.
- [ ] **S14-12 — Verify clean-install journeys and cross-machine handoff
  (requirements §§3–5):** On isolated clean installations without Docker, run
  user-facing install/start path and selected UI journeys, export a project,
  transfer its file and import manually on the second installation. Compare
  required evidence, receipts and usable outcomes; exercise restart/failure
  boundaries. Keep regression and Compose checks distinct from real proof.
- [ ] **S14-13 — Direct user experience gate before any `1.0.0` release:**
  Give the project owner/target user a runnable build and concise journey and
  transfer instructions. They personally install/start, traverse selected use
  cases and try export/import. Record observations, blockers and explicit
  pass/fail decision. Agent proxies, tests or screenshots cannot pass this
  gate; correct actionable findings and repeat the direct-user trial.

## Current Evidence Gate

- S14-01–07 passed task evidence review. S14-08 remains `[~]` pending a fresh
  evidence gate on its owner-approved unsigned closure scope and the exact
  reviewed-snapshot project checkpoint. Historical reviews E1/E2 failed under
  the previous full clean/signed scope; they are not new closure verdicts.
  The historical guide-only `UnsignedGuideEvidence` PASS is not a binary gate.
  The owner confirms installation on machine 2 and now states, “Xác nhận 4
  câu hỏi đều oke, có thể đóng task 8 rồi nhé. User confirmed.”
  Candidate identity, first-run/lifecycle, prerequisite handling, and
  uninstall/data retention are accepted as user-reported satisfactory checks;
  do not repeat them to reconfirm. Clean-Windows/signing and the precise
  skip-versus-vendor-UAC branch are not inferred from that confirmation.
- After retaining the full gate initially, the owner explicitly selected
  **“Đóng theo nghiệm thu unsigned”** for task closure. Clean-Windows/resource,
  signing, and the unreported real missing-runtime branch are retained as
  separate release gates, not silently marked passed. The unsigned 0.7.0-only
  exception and signed-update fail-closed policy are unchanged.
- The owner now prefers direct native iteration/testing on a second Windows
  workstation rather than provisioning or running a VM, to repair practical
  dependency issues quickly without VM setup complexity. The owner reports this
  machine has VS Code, npm, and Python; that makes any run there developer-host
  validation, not clean-install or clean-dependency proof. The second machine
  is not connected as a remote server, and no remote-server execution or VM
  provisioning is authorized. The manual installation guide is documented;
  second-machine installation and all four requested QA checks are now
  owner-confirmed. The
  accepted read-only VM survey remains historical planning evidence only; no
  guest was created or run.
- The owner authorized publication of 0.7.0 as a downloadable single easy-start
  installer and selected an unsigned pre-release for testing on the second
  Windows machine. No renewed publication authorization is needed. The hybrid
  PowerShell/build source changes are present. A local unsigned 0.7.0
  package/archive and NSIS candidate were built on 2026-10-02; scoped
  package/notice/import/runtime-exclusion audits passed. No candidate is
  published. Fresh review `S14-08-E20261002-A2`
  (`agent://S14HybridEvidence02`) resolved the earlier candidate-runtime and
  distributable-provenance findings, but full-task and bounded-publication
  verdicts were **FAIL** in that completed review, which predates the owner's
  four-check acceptance and explicit unsigned task-closure decision. A fresh
  applicable review and the exact-snapshot checkpoint are required before
  Main marks S14-08 `[x]`. No source rebuild or repeated owner trial is required
  merely to reconfirm accepted evidence.
- Fresh correction candidate **S14-08-W20261002-A2-R1** has embedded
  `runtime/source-provenance.json` (SHA-256
  `e1dfadbebde7c4eae55b2156576da13a7bb9df804fcbd8546f4f471cc6c99bd3`) with
  282 selected input-file hashes, base revision meaning, external runtime
  archive identities, and 17 derived-output groups. Its source input digest is
  `05d902983fe6e284f078802b3972bdce85105ea4c800fba5941bd33391679843`. The ZIP
  is 197,401,370 bytes (SHA-256
  `b5dcb57447c61b6b482e0c3634c92c799bb22a1d79a362b13a4f80ce19637fa5`); the
  compiled NSIS installer is 122,399,569 bytes (SHA-256
  `fbcc802be3063fb3aa1fe81376fa916599f87de9a0da50658b1691f0cfbefb85`,
  Authenticode `NotSigned`). Independent checks verified all 6,133 package
  payloads and ZIP content/CRC, all 332 indexed notices, source/provenance
  hashes, derived-output bindings, and omission of MSVC runtime DLLs from both
  frozen archives. Both artifacts remain unpublished and
  `releaseEligible=false`.
- The new R1 frozen manager was exercised on the existing developer host only,
  with unique `LOCALAPPDATA`/`APPDATA` and a candidate-local data root. The
  staged first-run path created only that isolated workspace; all four bundled
  services reported ready. A real browser journey selected an exact 0–115
  source span, validated its candidate, and recorded accepted manual receipt
  `df2dabd37704ccd4fe0c24e188c24d57fc557673b396fb6000eb1c7a11676eac`. The
  UI stated no model was called and the RM-63 authorization lock prevented
  assertion materialization. After graceful stop/restart, source revision 1,
  candidate revision 1, the exact span, validation, and accepted receipt
  remained visible. A loopback API-port collision returned `PORT_IN_USE`,
  started no services, and left the isolated workspace intact.
- Runtime module inspection found 95 dynamic-string occurrences across 30
  names; only `SHCORE.dll` matched the exercised dynamic candidates, from
  `C:\WINDOWS\System32\SHCORE.dll`. The other 29 names remain unobserved, not
  proven missing. Exercised launcher/PostgreSQL/Java/Python processes loaded
  MSVC runtime DLLs from `C:\WINDOWS\SYSTEM32`; this developer-host result is
  not clean-host dependency proof. The worker-host NSIS installer was not run: the
  process environment cannot redirect the shell Programs KnownFolder, while
  the installer creates Start Menu shortcuts and writes HKCU; the owner
  installation, workspace, and OS integration were left untouched.
- Earlier pre-hybrid host validation, lifecycle, restart/crash persistence,
  backup/restore rollback, PostgreSQL patch parity, dependency inventory and
  affected regressions remain historical evidence in
  `artifacts/sprint-14/task-08.md`; they do not validate a newly built hybrid
  package. Host validation is not clean-install proof.
- **Owner-confirmed launcher lifecycle (user-reported):** The owner confirmed,
  “Đã mở được, luồng start, mở browser, stop, running đều đúng. Confimed and
  continue.” This supersedes the earlier invisible-window blocker as reported
  baseline lifecycle evidence only. It does not identify the tested machine or
  establish this new installer's first-run, missing-VC, or clean-Windows path.
  No source fix or root cause is inferred.
- The former full S14-08 clean/signed prerequisites are now the explicitly
  open release gates below. They are not evidence that the candidate is
  signed, clean-host validated, or resource-certified. S14-12/S14-13 retain
  their own original clean-install and direct-user acceptance criteria.
- For R1, the native dependency inventory still records 340 x64 PE images with
  zero unresolved static/delay imports, but 95 dynamic-string candidate
  occurrences across 30 names are not proof of missing dependencies. During
  the exercised runtime, only `SHCORE.dll` was observed among those names,
  loaded from `C:\\WINDOWS\\System32\\SHCORE.dll`; the other 29 distinct names
  were not observed and remain unverified optional/string-only paths. The
  direct Microsoft download signature/product/version/SHA verification passed
  in the accepted earlier evidence; vendor execution and UAC were not
  exercised. The intended online prerequisite preserves Microsoft's own
  terms/UAC and per-user Projecta. The real missing-runtime branch remains a
  separate open release gate; other license terms remain binding. No private
  signing keys belong in the repository or chat.
- S14-09–13 and the end-of-sprint deep review cannot start until the S14-08
  evidence gate passes. A completed local hybrid package/archive and unsigned
  NSIS candidate now exist but are not published. The manifest is
  `releaseEligible=false` and has no Ed25519 or Authenticode signature. Task
  closure is limited to the owner-approved unsigned scope; no `1.0.0`
  approval, signed release, clean-install proof, or publication is implied.

## Deferred Release Gates — Owner-Approved S14-08 Closure

The owner selected “Đóng theo nghiệm thu unsigned” after accepting the four
machine-2 QA checks. This explicitly changes task closure, not the truth of
the missing evidence or the signed-update trust boundary.

- [ ] **RG14-NATIVE-CLEAN:** Prove the install/selected journey on resettable
  clean Windows 11 x64 as a standard user, with no Docker/development runtimes;
  close dependency coverage and measured minimum-resource requirements.
- [ ] **RG14-NATIVE-VC:** Exercise the actual absent/outdated-runtime vendor
  consent/UAC/install path and applicable cancellation/failure/restart
  boundaries. The owner-confirmed prerequisite handling does not identify
  whether that path ran or an existing runtime was skipped.
- [ ] **RG14-NATIVE-SIGN:** Supply owner-held Authenticode certificate,
  Ed25519 update-signing configuration, and timestamp service; produce and
  verify the corresponding signed artifact without weakening unsigned/update
  separation.

These gates remain required before the corresponding clean-certified,
signed/general release claim. Other third-party terms remain binding.
S14-12/S14-13 still need their planned evidence; no release or VM/remote-host
authorization is created here. The existing bounded unsigned 0.7.0
authorization is not broadened, and no asset is published by closing S14-08.

## Release Boundary and Notes

- All tasks start pending. Sprint planning does not authorize distribution,
  production enablement, an ontology release or a `1.0.0` tag. Completion of
  S14-13 is necessary but **not sufficient** for release: afterward, require a
  separate release-readiness decision on exact artifact/version, platforms,
  data scope, security, migration/recovery, regression/installation evidence,
  unresolved risks and the applicable explicit owner authorization before
  publishing. The existing authorization covers downloadable unsigned 0.7.0
  pre-release easy-start installers only; task closure does not publish an
  asset or clear the deferred release gates, and `1.0.0` remains a separate
  post-Sprint-14 release decision.
- Sprint 13's S13-08 offline evaluation/R6/R7, provider/human/held-out studies,
  successful local-model inference claims and production materialization stay
  outside this sprint without separate authority. The S14-13 owner product
  trial is a usability/release-readiness gate, **not** an independently governed
  business-quality study.
- Existing Compose-first development/CI and semantic/ontology decisions remain
  binding until an explicit approved change. Any ontology/SHACL change requires
  the project ontology skill and human semantic approval. No automatic Google
  Drive sync or extra connector breadth is implied.

## Owner-Authorized 0.7.0 Handoff

This bounded pre-release does not complete Sprint 14 or start S14-09.

- [x] Record direct native execution on the second Windows machine, without
  reusing remote-server configuration or provisioning a VM.
- [x] Commit scoped temporary Sprint 14 changes and push six reviewed source
  checkpoints to GitHub `main`, ending at `aefb457c44d17bfa61a3b045c63b62ad16eb6ad5`.
- [~] Produce one Windows 11 x64 per-user unsigned 0.7.0 pre-release installer
  with an easy normal launch/stop path, bundled dependencies and verified smoke.
- [~] Implement the owner-approved hybrid online installer: keep permitted
  bundled dependencies, omit the disputed app-local Microsoft VC++ binaries
  from distributed artifacts, and obtain a missing VC++ prerequisite directly
  from Microsoft's official source with version and publisher verification.
  The owner accepts Internet during installation and prerequisite UAC; keep
  Projecta itself per-user and do not elevate its services. Verify prerequisite
  detection, download failure, user cancellation, installation/restart outcomes,
  and the packaged launch lifecycle before the bounded publication review.
- [x] Provide manual download/install/start/stop instructions for the second
  machine in `unsigned-0.7.0-machine-install.md`; no repo clone or user-installed
  development runtime. The owner confirms installation and all four requested
  machine-2 QA checks, including post-install lifecycle and uninstall/data
  retention; this is user-reported acceptance, not clean-Windows/signing proof.
- [ ] After the bounded binary evidence review passes, publish the exact
  owner-authorized unsigned 0.7.0 asset with its checksum, notices, installation
  instructions, and truthful limitations. This publication decision does not
  clear the separate clean-Windows, real missing-VC, or signed-release gates.
- The owner-confirmed lifecycle above supersedes the invisible-window blocker;
  do not repeat the diagnostic request or infer a source fix/root cause. Binary
  publication still requires the approved hybrid cutover and bounded evidence
  review: remove all disputed VC runtime DLL copies, omit the Redistributable
  installer payload, and verify online Microsoft download/signature/version/
  integrity and prerequisite-only UAC disclosure. No tag, release, or asset is
  authorized before that review. The exact local candidate and provenance are
  recorded in `artifacts/sprint-14/task-08.md`; S14-08 remains `[~]`.
