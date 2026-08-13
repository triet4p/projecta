# Task Summary: S11-A09 — Map GitHub Issue-Comment Observations

**Sprint:** Sprint 11

**Task:** S11-A09

## Summary of Work

Added deterministic issue-comment mapping that accepts only a proven bound issue
parent, excludes pull-request or unknown parents, validates the issue URL,
retains bounded comment body and parent number, and reuses the same opaque
revision-aware canonical event boundary.

## Testing

* **Test File:** `apps/api/tests/test_sprint11_github_mapping.py`
* **Status:** Passed in the combined A08/A09 mapping suite.
