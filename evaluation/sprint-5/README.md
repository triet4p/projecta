# Sprint 5 Evaluation Dataset

**Dataset version:** `s5.v1`
**Status:** synthetic development fixture; no production or sensitive data.

`dataset.v1.json` contains representative Quick Notes and expected normalized
gold annotations. Offsets are zero-based, half-open Unicode code-point ranges
against the exact `rawText` value in each case. `expected: []` is a valid gold
outcome for abstention/empty extraction. The replay adapter and offline runner
must treat the dataset as read-only.

Each case includes a slice/category so evaluation can report supported type,
relation, link, Unicode, ambiguity, empty, and adversarial results separately.
