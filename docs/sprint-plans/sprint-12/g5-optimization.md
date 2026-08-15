# Sprint 12 G5 Optimization Packet

**Status:** `G5_PREPARATION_DEVELOPMENT_OPEN`

The packet binds controlled development-only experiments to the approved
G4 measurement boundary. The supersession prompt experiment was authorized and
executed on the v2 development corpus, but no candidate was selected and no
held-out data was inspected because the 32-case stability follow-up failed.

This authorization covers measurement repair and bounded development runs only;
it does not authorize validation, full-corpus execution, candidate freeze or
held-out evaluation.

## Bound evidence

- Registry: `evaluation/sprint-12/optimization/experiment-registry.v2.json` /
  `sha256:cd4594a1a0dff78f44b5da2136392d428caa43cbabee3ea1185fe7c772b0a7fe`
- Executable validator: `REGISTRY_VERSION = s12.experiment-registry.v2`; the
  persisted registry passes `validate_registry()` in the Phase F regression
  suite.
- Dataset manifest: `s12.corpus.atomic.v2` /
  `sha256:030087614d30c821a0d03c8d5bf0a549b63fc6ba672531e8eda37f474265f32a`
- Execution registry status: `s12-f-01 = COMPLETED_STABILITY_FAILED`; the
  registered one-run stopping rule was amended and the variance is recorded in
  the registry rather than rewritten as history.
- S12-73 evidence: `s12-73-prompt-supersession.v1.json` and
  `s12-73-prompt-followup-stability.v2.json` /
  `sha256:b5660ae919330b2fb94529d347581e2a043fc63df7e79020590ee088c27a5943`
- Targeted diagnostic: `s12-73-targeted-diagnostics.v1.json` /
  `sha256:90ea3443dde91a8b21f4a9be590017d96b81e0afb34bb3ac90ac4821e3c8d48b`;
  one no-retry attempt on `s12-a-0153` and `s12-a-0187`, with no failure
  reproduced and no raw payload retained.
- Baseline configuration: `sha256:2f4a4c84984fefd1d6ab502a5e73a70bf37ef92e416336392acc2227fa1a5cb2`
- Baseline status: `RUNTIME_BACKED_WITH_FAILURES`
- Registered experiments: `5`

## Measurement state

- Candidate state: `AVAILABLE_BUT_STABILITY_FAILED`
- Comparison state: `REJECTED_CANDIDATE_HARD_INVARIANT`
- Hard invariants: `FAIL` (`3 schema_invalid`, `0 invalid_evidence`)
- Held-out inspected: `False`
- Development experiments authorized: `True`
- S12-73 prompt-only development experiment: executed; candidate not promoted
- S12-73 follow-up: 32 cases x 3 runs, `3 schema_invalid`, `0 invalid_evidence`;
  stability gate failed; candidate was not promoted
- Optimization authorized: `False`
- Cost/latency and slice results: `NOT_AVAILABLE`

## G5 acceptance checklist

- [x] Registry requires hypothesis, development split, configuration
  digests, metric target and stopping rule.
- [x] Single-dimension change and preserved governance artifacts are
  validated for prompt, context, agent-workflow, tool and model records.
- [x] Candidate selection fails closed unless exactly one scored candidate
  passes the multi-metric rule and hard invariants.
- [x] Candidate freeze binds experiment, configuration and registry digests.
- [x] Draft G5 packet is prepared.
- [x] S12-73 supersession prompt experiment is executed on the development slice.
- [ ] Candidate passes the 32-case guarded-prompt stability follow-up.
- [ ] Candidate is evaluated on validation after development selection.
- [ ] Human reviewers approve one candidate or record no-go.

## Approval boundary (S12-83)

`APPROVED_WITH_LIMITATIONS`; this approval records a no-go decision
and authorizes development experiments only; validation, freeze and
held-out evaluation still require a candidate with passing hard invariants.
