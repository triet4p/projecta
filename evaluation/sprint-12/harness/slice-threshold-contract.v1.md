# S12 slice-threshold contract v1

Status: `FROZEN_FOR_NEXT_PREREGISTRATION_NO_PROVIDER`.

This artifact versions slice labels, denominators, primary/secondary
statistics, thresholds and zero-denominator behavior before a new Stage A.
Missing output remains in the denominator with zero score. A required metric
with an unversioned label or zero denominator fails closed.

The next tool comparison must use one captured provider response per
case/run, branch it through both post-processing arms, use three independent
runs with no retry, and keep validation/held-out custody closed.
