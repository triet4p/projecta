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
  Package required services/dependencies behind the approved install/start/stop
  route with clear readiness and failure feedback. Prove a clean installation
  with **no Docker installed** opens localhost and runs a selected journey;
  preserve the developer/CI path.
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

- S14-01–07 passed task evidence review. S14-08 remains `[~]`; package and
  binary evidence remains **FAIL / do not advance**. The separate bounded guide
  usability/provenance review (`UnsignedGuideEvidence`) **passed**; it verifies
  documentation only and clears none of the binary-publication gates.
  Manual installation and first-run execution on the second machine remain
  unverified.
- The owner retained the full S14-08 signed-install gate, then explicitly
  approved an unsigned exception only for the downloadable 0.7.0 pre-release.
  That exception does not pass S14-08 or authorize `1.0.0`.
- The owner now prefers direct native iteration/testing on a second Windows
  workstation rather than provisioning or running a VM, to repair practical
  dependency issues quickly without VM setup complexity. The owner reports this
  machine has VS Code, npm, and Python; that makes any run there developer-host
  validation, not clean-install or clean-dependency proof. The second machine
  is not connected as a remote server, and no remote-server execution or VM
  provisioning is authorized. The manual installation guide is documented;
  actual second-machine install/start execution remains unverified. The
  accepted read-only VM survey remains historical planning evidence only; no
  guest was created or run.
- The owner authorized publication of 0.7.0 as downloadable single easy-start
  installers and selected an unsigned pre-release for testing on the second
  Windows machine. Build a real installer and normal launch path; the existing
  host-validation development override is not an acceptable user install route.
  Disclose unsigned publisher warnings, checksums, bundled dependency notices,
  and the absence of clean-install proof. Keep signed release/update verification
  fail-closed outside this explicit 0.7.0 exception. No renewed publication
  authorization is needed. Installer implementation and publication are pending.
- The corrected frozen native package, real host Journey 1, restart/crash
  persistence, backup/restore rollback, PostgreSQL patch parity, dependency
  inventory and affected regression checks have verified evidence in
  `artifacts/sprint-14/task-08.md`. Host validation is not clean-install proof.
- Remaining prerequisites: a resettable clean Windows 11 x64 standard-user
  environment without Docker or preinstalled development runtimes; owner-held
  Authenticode and Ed25519 signing configuration with timestamp service; and
  owner redistribution clearance for the staged runtime/license inventory.
  Clean-OS dependency closure and minimum resource measurements require that
  environment. No private signing keys belong in the repository or chat.
- S14-09–13 and the end-of-sprint deep review cannot start until the S14-08
  evidence gate passes. The current package is unsigned, host-validation-only
  and non-distributable; it is not the owner-authorized 0.7.0 publication
  artifact. No `1.0.0` release approval, signed artifact, or clean-install proof
  is implied.

## Release Boundary and Notes

- All tasks start pending. Sprint planning does not authorize distribution,
  production enablement, an ontology release or a `1.0.0` tag. Completion of
  S14-13 is necessary but **not sufficient** for release: afterward, require a
  separate release-readiness decision on exact artifact/version, platforms,
  data scope, security, migration/recovery, regression/installation evidence,
  unresolved risks and the applicable explicit owner authorization before
  publishing. The existing authorization covers downloadable unsigned 0.7.0
  pre-release easy-start installers only; the full S14-08 gate remains
  independent, and `1.0.0` is a separate post-Sprint-14 release decision.
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
- [x] Provide manual download/install/start/stop instructions for the second
  machine in `unsigned-0.7.0-machine-install.md`; no repo clone or user-installed
  development runtime. Actual second-machine execution remains unverified.
- [ ] After the GUI first-run and VC++ REDIST prerequisites are resolved and
  the bounded binary-publication review passes, tag the exact source revision
  and publish the pre-release with installer, checksums, notices, installation
  instructions and truthful limitations.
- Binary publication is blocked by `V070InstallerEvidence`: the owner must
  complete the corrected GUI first-run workspace form, observe all four services
  ready and a usable browser, and stop them; automated desktop focus was
  unavailable. Also resolve the specific Microsoft VC++ REDIST licensing
  condition for the five packaged DLLs before public binary distribution.
  The source push passed `V070SourcePushEvidence`; no tag/release/asset was
  published. The local candidate installer is
  `build/releases/Projecta-Setup-0.7.0-win-x64-unsigned-prerelease.exe`, SHA-256
  `f7555a90807bff34540a89758e5f8fe5853b8cbd09d3772d40ac4c9d77a64a77`.
