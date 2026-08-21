# S12-f-09 scoring erratum

Status: `ERRATUM_ISSUED_WITHOUT_RERUN`.

The raw six-run aggregate, repaired v2 report, and all six run reports remain immutable. This erratum is offline-only and does not authorize Stage B or candidate selection.

## Corrected contract

- Missing outputs retain the gold relation denominator and receive zero relation true positives.
- Evidence support/exact are pooled ratios: summed numerator divided by summed semantic true positives.
- The preregistered `abstentionF1Minimum` is evaluated as binary positive-class F1; accuracy is diagnostic only.
- Relation semantic floor is checked for both macro and micro because the preregistration did not specify which statistic it meant.
- The required slice floor is `NOT_EVALUATED` because no versioned slice thresholds were bound before execution; therefore it cannot pass.

## Corrected evidence

- Control valid case-runs: `136/144`; candidate: `141/144`.
- Control semantic micro F1: `0.072727`; candidate: `0.037037`.
- Evidence support: control `2/2`, candidate `1/1`.
- Evidence exact: control `2/2`, candidate `1/1`.

## Limitations

- Comparison integrity is `DEGRADED_INDEPENDENT_STOCHASTIC_OUTPUTS`: the two arms did not branch one captured provider response.
- The live candidate path omitted the optional trigger quote, so the required-trigger fail-closed path was not exercised.
- The immutable reports contain no `unmatchedPredicate` bucket; future instrumentation must make any predicted-side overlap explicit.
- The authorization commit did not contain the complete f09 execution package; artifact digests preserve evidence integrity but do not retroactively create a frozen commit.

Decision: `COMPLETED_REJECTED_NO_STAGE_B_NO_SELECTION`.
