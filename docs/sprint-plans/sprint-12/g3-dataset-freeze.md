# Sprint 12 G3 Dataset Freeze Review Packet

**Status:** `G3_APPROVED_G4_PENDING`

**Gate:** G3 — Dataset Freeze

**Decision:** G3 is approved by the project owner with explicit limitations.
The repository-visible Phase D fixture passes structural, privacy, provenance,
coverage and leakage checks, but human QA, human adjudication and test custody
remain incomplete. These limitations must be closed before any production-scale
dataset or annotation-reliability claim.

## 1. Dataset boundary

| Artifact | Scope | Status |
| --- | --- | --- |
| `corpus/atomic-development-validation.v1.json` | 160 repository-visible development/validation atomic cases | Synthetic preparation fixture |
| `corpus/scenario-development-validation.v1.json` | 18 repository-visible development/validation episodes | Synthetic preparation fixture |
| `corpus/manifests/development-validation.manifest.v1.json` | 200 atomic and 18 scenario IDs with digests | Frozen fixture manifest |
| `corpus/manifests/test-custody.manifest.v1.json` | 40 atomic and 6 scenario test digests only | Custody not established |
| `corpus/gold/*.json` | Atomic, scenario, retrieval and business-review gold shapes | Synthetic fixture only |
| `corpus/qa/*.json` | Independent QA and adjudication boundary | Human work pending |

The coverage target is 200 atomic cases (120 development, 40 validation, 40
test) and 24 scenarios (12 development, 6 validation, 6 test). Test payloads
and gold are intentionally absent from the repository and are represented only
by counts, schema versions and cryptographic digests.

## 2. Validation evidence

- [x] Atomic schema shape, source digests and evidence spans validate for the
  repository-visible payload.
- [x] Scenario schema shape, event manifests and checkpoint references validate
  for the repository-visible payload.
- [x] Synthetic privacy and prohibited-token scan passes.
- [x] Journey, language, split and mandatory-slice coverage passes structurally.
- [x] Exact duplicate and high-similarity leakage scan passes for the available
  development/validation payload.
- [x] Development/validation manifest is digest-bound and frozen as a fixture.
- [ ] Human QA independently annotates validation/test and the approved
  development sample.
- [ ] A qualified reviewer adjudicates all material final-gold disagreements.
- [ ] Human data owner establishes custody for the sealed test bundle.

Validation command:

```text
uv run --script scripts/validate_sprint12_phase_d.py
```

Expected result is `PASS_WITH_HUMAN_GATES_PENDING`; the G3 approval records this
as a limitation and does not relabel the fixture as human dataset evidence.

## 3. G3 acceptance checklist

- [x] S12-40 through S12-48 preparation artifacts exist.
- [x] S12-51 through S12-54 repository-visible validation and freeze artifacts
  exist.
- [x] S12-56 draft G3 packet is prepared.
- [ ] S12-49 independent QA annotation is complete.
- [ ] S12-50 final human adjudication is complete.
- [ ] S12-55 test split is sealed under human custody.
- [x] Project owner approves G3 with the limitations recorded above.
- [ ] Human data reviewer accepts the exact dataset version.
- [ ] Semantic reviewer accepts the exact gold and residual semantic gaps.

The approval authorizes G4 preparation only. It does not establish human QA,
human adjudication, test custody or held-out unlock authority.

## 4. Approval record (S12-57)

| Field | Value |
| --- | --- |
| G3 outcome | `APPROVED_WITH_LIMITATIONS` |
| Dataset version | `s12.corpus.v1` |
| Project owner | Explicit approval recorded in Codex task on 2026-08-14 |
| Data reviewer | _Awaiting human custody and QA evidence_ |
| Semantic reviewer | _Awaiting final gold review_ |
| Authorization after approval | Proceed to G4 preparation only; no held-out unlock before G6 |
