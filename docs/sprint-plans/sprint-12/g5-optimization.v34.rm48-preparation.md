# G5 optimization v34 — RM-48 offline comparison preparation

**Status:** preparation only; pending S12-RM-49 owner review  
**Date:** 2026-08-22

RM-48 produced a deterministic, sanitized v6/v9 comparison at
`evaluation/sprint-12/optimization/s12-f-12-rm48-error-comparison.v1.json`.
The artifact binds the immutable v6 digest
`sha256:419ac3c7aa7fad06287b231432d1ae167990ece45ca11ef94882fb6139569233`
and v9 digest
`sha256:84cb0667b8ee3469be5bdd4c3545a41012ba46bb07071508c41dca76fbf3761e`.

The comparison reconciles 144 calls and zero retries in each report. Schema
invalid decreased from 6 to 5, while invalid evidence increased from 17 to 20.
The v9 finite diagnostics identify 14 trigger-containment and 6
endpoint-containment failures. Gold-relations remains a clean control in both
reports, but that does not waive candidate hard gates or prove causality.

The packet distinguishes observed behavior changes from improved observability:
v6 retained no finite historical reason, while v9 records registered sanitized
reason codes. It does not reconstruct provider payload/source or claim provider,
prompt or runtime causality. Three bounded options are recorded: offline finite
diagnostic hardening, offline materializer/scorer parity fixtures, or stopping
provider experimentation. None is authorized by RM-48.

The non-authoritative snapshot is
`evaluation/sprint-12/current-state-next-rm48.v1.json`; the prepared G5 packet
is `evaluation/sprint-12/optimization/g5-packet.v34.rm48-preparation.json`.
RM-49 must independently review this packet before any implementation, lineage,
authorization or provider work.

All provider execution, rerun/retry, remediation implementation, lineage
preparation, validation, held-out access, Stage B, selection and promotion
remain false.
