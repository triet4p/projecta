# Task Summary: S5-27 — Build the offline evaluation runner

**Sprint:** Sprint 5
**Task:** S5-27

## Summary of Work

Added a credential-free deterministic runner that loads the versioned dataset
and replay outputs, fails on missing cases, computes schema validity,
precision/recall/F1, exact spans, abstention precision/recall, bounded
cross-project rejection, and applies safety/quality thresholds in a redacted
JSON report. It does not call a provider or include raw prompts in output.

## Files Modified

- `evaluation/sprint-5/run_offline.py`
- `evaluation/sprint-5/test_run_offline.py`

## Testing

- **Command:** `python -m pytest evaluation/sprint-5/test_run_offline.py -q`
- **Current result:** passed with the complete `s5.replay.v1` fixture.
