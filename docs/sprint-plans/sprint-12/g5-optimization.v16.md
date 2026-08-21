# Sprint 12 G5 Optimization Next-State Preparation v16

**Role:** non-authoritative offline next-state preparation

**Current owner state remains:** `G5_F12_CLOSED_REJECTED_OFFLINE_REMEDIATION_PREPARATION_ONLY`

RM-28 analyzed the immutable f12 Stage A report without provider execution or
held-out access. The report digest remains
`sha256:419ac3c7aa7fad06287b231432d1ae167990ece45ca11ef94882fb6139569233`.

## Proven findings

- Six schema-invalid responses: five `predicted-entities` Stage 1 and one
  `gold-entities` Stage 2.
- Seventeen `gold-entities` evidence findings, all `unsupported` while their
  semantic disposition is `exactMatch` and endpoint resolution is `34/34`.
- The `gold-relations` integrity control has zero invalid-evidence findings and
  zero materializer failures.
- Exact malformed fields, validation paths and provider/prompt causality are
  unavailable from the sanitized report and remain explicitly unknown.

## Bound offline artifacts

- `evaluation/sprint-12/optimization/s12-f-12-rm28-offline-remediation.v1.json`
- `evaluation/sprint-12/optimization/s12-f-12-rm28-diagnostic-contract.v1.json`
- `scripts/s12_f12_rm28_offline_diagnostics.py`

The proposed next package adds finite sanitized schema/evidence reason codes,
runtime-only evidence materialization diagnostics and typed endpoint accounting.
It does not modify the frozen report or historical lineage.

## Governance boundary

`providerExecutionAuthorized=false`; no preregistration, technical freeze,
authorization, validation, held-out access, Stage B, candidate selection or
promotion is issued. The exact next gate is owner review of the offline package.
