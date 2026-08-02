# Task Summary: S5-28 — Add opt-in live provider evaluation

**Sprint:** Sprint 5
**Task:** S5-28

## Summary of Work

Added a separate live evaluation command targeting the configured DeepSeek
OpenAI-compatible Responses endpoint. It requires both requested credential
and model configuration, skips cleanly otherwise, runs the versioned dataset
only when explicitly opted in, and emits aggregate completion/error-class
metadata without raw notes, prompts, provider payloads, or secrets. Canonical
CI remains offline-only.

## Files Modified

- `evaluation/sprint-5/run_live.py`
- `evaluation/sprint-5/test_run_live.py`

## Testing

- **Command:** `python -m pytest evaluation/sprint-5/test_run_live.py -q`
- **Coverage:** missing-credential skip path; no live request was made.
