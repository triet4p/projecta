# Sprint 12 G5 Optimization Packet

> Historical gate snapshot, superseded for current state by
> [G5 Optimization Packet v17](g5-optimization.v17.md). Do not rewrite this
> packet's original decision.

**Status:** `G5_PREPARATION_DEVELOPMENT_OPEN`

The packet binds controlled development-only experiments to the approved
G4 measurement boundary. The supersession prompt experiment and the S12-77
model comparison were authorized and executed on the v2 development corpus,
but no candidate was selected and no held-out data was inspected.

This authorization covers measurement repair and bounded development runs only;
it does not authorize validation, full-corpus execution, candidate freeze or
held-out evaluation.

## Bound evidence

- Registry: `evaluation/sprint-12/optimization/experiment-registry.v5.json`
  (binds S12-77, S12-f-06, targeted diagnostics, and the S12-f-06 erratum); the persisted registry
  passes `validate_registry()` in the Phase F regression suite.
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
- Registered experiments: `6`

## Measurement state

- Candidate state: `NO_CANDIDATE_PROMOTED`
- Comparison state: `DEGRADED_UNEQUAL_VALID_OUTPUTS_SEMANTIC_FAIL`
- S12-f-06 hard gates: candidate `PASS`; control `FAIL` (`1 schema_invalid`,
  `1 missing output`).
- S12-f-06 semantic gates: `FAIL`; common valid-case erratum covers `23`
  paired case executions and confirms regression.
- Held-out inspected: `False`
- Development experiments authorized: `True`
- S12-73 prompt-only development experiment: executed; candidate not promoted
- S12-73 follow-up: 32 cases x 3 runs, `3 schema_invalid`, `0 invalid_evidence`;
  stability gate failed; candidate was not promoted
- S12-77 Stage A: `deepseek-v4-pro` versus `deepseek-v4-flash` on 16 cases x
  3 paired runs; candidate hard gates `PASS`, control hard gates `FAIL`, and
  semantic gates `FAIL`, so Stage B is locked.
- S12-77 targeted diagnostic: one no-retry attempt on `s12-a-0121` and
  `s12-a-0176` reproduced neither failure (`failureCounts = {}`). This is
  stochastic non-reproduction, not evidence that the candidate is stable.
- S12-f-06 sampling preregistration: explicit `temperature=0.0` and `topP=1.0`
  for the same `deepseek-v4-pro` model is registered as a development-only
  experiment. Stage A executed after approval: candidate had `0 schema_invalid`
  but entity, abstention and relation metrics regressed; no candidate was
  selected and Stage B remains locked. The candidate branch is now closed; no
  further Pro model or sampling sweep is authorized.
- Optimization authorized: `False`
- Latency and usage: available in the run reports; pricing-based cost:
  `NOT_AVAILABLE_PROVIDER_PRICE_CONFIGURATION`.

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
