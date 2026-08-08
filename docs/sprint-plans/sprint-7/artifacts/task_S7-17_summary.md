# S7-17 — LLM profile repository

Implemented project-scoped non-secret profile persistence with active selection,
revision increments, audit timestamps, and optimistic revision conflict
protection. Secret references remain internal and foreign-key constrained.

Validation: stale-revision repository test passes.
