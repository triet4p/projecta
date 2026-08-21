# Sprint 12 Dataset Contract

**Base contract version:** `s12.v1`; current visible corpus: `v3-frozen`

**Current Sprint status:** `G5_F12_SUPERSEDING_LINEAGE_PREPARATION_APPROVED_OFFLINE_ONLY`

The repository-visible pilot and development/validation gold now have
owner-delegated AI semantic review. They remain agent-authored synthetic data
with `humanEvidence: false`. G3.1-A/B/C are complete with scope limits. The f12
preregistration/freeze lineage was issued and one exact 144-call development
Stage A execution completed. RM-27 closed f12 rejected after hard, threshold
and slice failures; RM-29 permitted offline diagnostic/remediation
implementation and RM-31 now permits preparation of a new superseding lineage
only. No new preregistration or freeze is issued, and no candidate is selected.
G6 separately remains blocked by test custody and candidate quality. See
`current-state.v1.json` for the authoritative index.

This directory contains the governed contract for the Sprint 12 business
semantic benchmark. It does not contain the held-out test cases or gold. Test
inputs and annotations remain under human custody until the approved G6
procedure permits one blinded run.

## Contract artifacts

- `schema/atomic-case.schema.json` defines one independently addressable note
  case and its atomic semantic gold.
- `schema/scenario-case.schema.json` defines one ordered project episode,
  graph checkpoints, review decisions and grounded competency answers.
- `coverage-matrix.v1.json` binds the G0 journeys to minimum quotas and slices.
- `annotation-guide.v1.md` is the base guide;
  `pilot/annotation-guide.v1.1.md` records the pilot clarification used by the
  owner-delegated synthetic review track.
- `data-governance.v1.md` defines provenance, licensing, privacy, retention,
  leakage, split and custody controls.
- `metrics.v1.md` defines deterministic scoring and reporting behavior.
- `harness/metric-contract.v2.json` and `harness/metrics.v2.md` freeze the
  separated relation semantic, evidence-support and exact-span metrics for
  the G3.1 remediation track; the v1 contract remains historical.
- `scripts/sprint12_leakage_validator.py` (run from the repository root) applies
  v2 canonical template, exact-content, and scenario-lineage leakage checks to
  visible development/validation payloads without reading held-out test data.
- `scripts/sprint12_language_validator.py` audits declared language metadata
  with conservative offline signals and excludes every slice lacking qualified
  independent review; it also never reads held-out test data.
- `scripts/sprint12_scenario_validator.py` checks repeated source lineages for
  unexplained temporal, review, checkpoint, and competency-answer conflicts;
  it rejects test payload input.
- `scripts/sprint12_g31_measurement_readiness.py` binds the repaired metric,
  evaluator, diagnostic validators, test evidence and residual limitations for
  G3.1-A while keeping provider execution explicitly unauthorized.
- `corpus/v3/atomic-deep-pilot.v1.json` and its manifest contain the new 48-case
  R09 pilot across six lineages; R12 quality and R13 scoped approval are
  complete.
- `corpus/v3/scenario-deep-pilot.v1.json` and its manifest contain the R10
  longitudinal pilot: six unique eight-event episodes, split 4 development / 2
  validation by lineage, with independent checkpoints, contradiction tracking
  and competency-answer fixtures; R12 quality and R13 scoped approval are
  complete.
- `corpus/v3/gold-adjudication.v1.json` records the R11 owner-delegated AI
  annotation/adjudication packet for all 48 atomic cases and six scenarios,
  including rule IDs, explicit coverage, digests and zero material disputes;
  qualified human evidence remains false; R13 approved only the bounded
  owner-delegated synthetic track.
- `gates/g3.1-b-v3-pilot-quality.v1.json` records the R12 offline quality gate:
  schema, provenance, spans, language, scenario consistency and visible split
  leakage all pass, while test custody remains uninspected.
- `gates/g3.1-b-pilot-approval.v1.json` records R13 approval with scope limits:
  only passed v3 patterns may scale; provider, held-out, G5 and business-quality
  authorization remain false. Pilot gaps for J7/J8, `resolves`, `Assumption` and
  `ResearchFinding` are explicit.
- `corpus/v3-scale/` contains the additive R14 scale track: 208 atomic cases
  across 26 unique lineages and 26 scenarios, split 160 development / 48
  validation with zero test payload; R15 freeze and QA are complete.
- `corpus/v3-frozen/` is the R15 frozen development/validation bundle with
  immutable payload/manifests, coverage, provenance, leakage and QA evidence;
  G3.1-C readiness is approved with scope limits and the bundle contains no
  test payload.
- `gates/g3.1-c-v3-readiness.v1.json` approves one scoped validation run and
  controlled development for represented J1–J6 extraction slices only; it does
  not claim full benchmark completeness or authorize provider/held-out access.
- `optimization/s12-f-02-04-v3-supersession.v1.json` closes the old context,
  agent-workflow and generic-tool registrations against the v2 manifest without
  mutating their historical registry entries; the replacement path is f09 on
  frozen v3, still execution-locked.
- `apps/api/src/projecta_api/extraction/relation_evidence.py` owns deterministic
  relation evidence boundaries from canonical endpoint spans and an optional
  trigger quote; invalid, missing or ambiguous context fails closed.
- `optimization/s12-f-09-relation-evidence-preregistration.v1.json` binds the
  frozen v3 dataset, current evaluator/metric contract, pricing, control prompt
  and server-owned tool; it changes only `tool` and remains execution-locked.
- `optimization/s12-f-09-authorization.v1.json` records the explicit bounded
  owner authorization for Stage A only; held-out, retry and Stage B remain
  prohibited.
- `optimization/s12-f-09-relation-evidence-stage-a.v1.json` preserves the raw
  six-run execution aggregate and 288 development case-runs. The candidate is
  rejected for Stage B because hard gates and absolute quality floors failed.
- `optimization/s12-f-09-relation-evidence-stage-a.v2.json` is the offline
  denominator-repaired decision report and remains immutable historical
  evidence.
- `optimization/s12-f-09-relation-evidence-stage-a.v3.json` and
  `optimization/s12-f-09-scoring-erratum.v1.*` are the offline closure
  correction: missing outputs retain gold denominators, evidence ratios use
  pooled numerators, preregistered gate names are restored, and the required
  but unthresholded slice floor is fail-closed.
- `optimization/experiment-registry.v11.json` and
  `optimization/g5-packet.v11.json` close f09 as `NO_SELECTION`; they bind the
  authorization, raw/v2/v3 reports, erratum, six run reports and accounting.
- `optimization/s12-f-09-remediation-track.v2.*` records offline RM-01 through
  RM-03 completion; v1 remains historical. The track opens preparation only for a
  shared-response comparison, versioned slice thresholds, a decided
  trigger-quote contract, and a complete authorization-bound execution package.
  It does not authorize a provider call or reopen f09.
- `optimization/s12-f-12-rm23f-issuance-transition.v1.json` records the later
  issuance of the exact f12 v7 preparation lineage without mutating its
  historical `PREPARED` fields.
- `optimization/g5-packet.v19.json` is the current G5 machine packet. It keeps
  selection at `NO_SELECTION`, permits offline preparation of a new
  superseding lineage, and leaves issuance and provider execution closed.
- `optimization/g5-packet.v20.rm32-offline-preparation.json` and the RM32 v8
  artifacts are non-authoritative preparation snapshots pending RM-33 owner
  issuance review; they issue nothing and perform zero provider calls.

## Dataset contract rules

- Every case has a stable ID, schema version, origin, language, sensitivity,
  permission reference, split and content digest.
- Every evidence span uses zero-based, half-open Unicode code-point offsets and
  must reproduce the exact source slice.
- Gold uses released extraction types and relation predicates. Unsupported
  concepts are recorded as semantic gaps rather than force-fit.
- Model-assisted drafts require human rewriting and independent annotation.
- Validation and test cases are double-annotated and materially disputed cases
  are adjudicated by a third qualified reviewer.
- Development and validation artifacts may be repository-local only when they
  satisfy the privacy, provenance and leakage rules. Test payloads and gold are
  not stored in this repository.

## Current gate

G0 and G1 are approved; G2 and G3 are approved with recorded limitations;
G3.1-A/B/C are complete with scope limits. G4 now has a runtime-backed baseline
with failures and G4.1 is contract-aligned but stability-failed. G5 has issued
the exact f12 preregistration/freeze lineage, while provider authorization,
Stage A output and candidate selection remain absent. G6 is blocked by missing
external test custody and a frozen passing candidate; held-out inputs/gold
remain outside the repository.
