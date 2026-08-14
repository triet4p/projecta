# Sprint 12 Annotation Pilot

**Pilot version:** `s12.pilot.v1`

**Status:** `AGENT_GENERATED_CALIBRATION_FIXTURE_PENDING_HUMAN_REVIEW`

This directory contains a synthetic calibration fixture for testing the Phase C
annotation workflow. It is not evidence that qualified human annotators have
achieved G2 agreement.

## Contents

- `atomic-pilot.v1.json` — 20 synthetic atomic cases spanning released types,
  multilingual text, ambiguity, semantic gaps, hostile instructions,
  cross-project isolation and noisy input.
- `scenario-pilot.v1.json` — three five-event longitudinal episodes with graph
  checkpoints and grounded questions.
- `calibration-protocol.v1.md` — common examples, qualification and isolation
  procedure.
- `labels/annotator-a.v1.json` and `labels/annotator-b.v1.json` — isolated
  fixture label sets; they are not human annotation records.
- `agreement-report.v1.json` — deterministic fixture agreement report.
- `adjudication-log.v1.json` — fixture disagreements and accepted outcomes.
- `annotation-guide.v1.1.md` — guide revisions derived from the fixture.

Before G2 approval, a data/annotation owner must replace or supplement the
fixture with two independently produced human label sets, verify qualifications
and conflicts, and rerun the agreement procedure without shared intermediate
answers.
