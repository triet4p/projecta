# S7-22 — Operation-time gateway resolution

Extraction now resolves an immutable runtime configuration snapshot per
operation and builds the gateway from that snapshot. Profile revisions can
change without restart, while an in-flight operation keeps one model and
credential configuration.

Validation: existing M3 extraction regressions remain passing.
