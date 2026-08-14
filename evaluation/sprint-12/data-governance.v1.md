# Sprint 12 Data Governance and Custody Contract v1

**Status:** `G1_PROPOSED`

## Provenance and licensing (S12-19)

Every case must record:

- stable case/scenario ID and schema version;
- authoring origin: human-authored synthetic, model-assisted rewritten,
  authorized de-identified or public licensed;
- authoring organization/person reference held in the restricted review log;
- source language, source style, sensitivity class and creation date;
- license or permission reference and permitted-use scope;
- content digest computed over canonical UTF-8 source bytes; and
- annotation guide, annotator role, annotation timestamps and adjudication
  references outside the raw case payload.

Model-assisted drafts must be labeled, rewritten by a qualified human and
independently annotated. A model response, prompt or provider payload is not a
license and is not sufficient provenance.

## Privacy, retention and deletion (S12-20)

- Primary authoring source is synthetic and must contain no real customer,
  work-tenant, personal, secret or production payload.
- Authorized de-identified material requires documented owner authorization,
  lawful basis/consent where applicable, de-identification review, retention
  end date and deletion owner before ingestion.
- Names, emails, tokens, credentials, private URLs, account IDs and unique
  customer identifiers are prohibited unless a reviewer has explicitly marked
  them as synthetic placeholders.
- Development/validation artifacts in the repository must be sanitized and
  contain no restricted raw payload.
- Test inputs and gold remain outside the agent-visible repository under human
  custody until the G6 unlock procedure.
- Deletion or withdrawal invalidates the affected manifest and every result
  digest that includes the case; silent replacement is forbidden.
- Suspected disclosure pauses authoring/evaluation, preserves the audit record,
  removes exposed payloads through the approved operator procedure and opens a
  breach review before resealing.

## Leakage threat model (S12-21)

| Threat | Control | Failure response |
| --- | --- | --- |
| Exact duplicate across splits | Canonical text digest and split-wide duplicate check | Remove or reassign before freeze |
| Near duplicate/paraphrase leakage | Token/character shingles plus human review of high-similarity pairs | Hold affected cases, adjudicate split |
| Same scenario in multiple languages | Shared scenario lineage and cross-language grouping | Keep all variants in one split unless G1 records a reason |
| Prompt contamination | Search prompts, fixtures, docs and model context for test identifiers/content | Remove contamination and invalidate exposed holdout |
| Model memorization | Record public/licensed origin and exclude recognizable private payloads | Downgrade claim or remove case |
| Agent exposure | Test bundle is not stored in repository or agent-visible runtime | Seal again; invalidate any run after exposure |
| Gold leakage through logs | Safe-log scan and denylist for source text, labels and test IDs | Delete artifact, rerun from clean custody |
| Metric cherry-picking | Reports require all cases/slices including failures and omissions | Reject report and candidate gate |

## Split and custody (S12-22)

Atomic cases use 60% development, 20% validation and 20% test. Scenario cases
use 12 development, 6 validation and 6 test episodes. Stratification occurs by
journey, language, semantic slice, source style, ambiguity/threat class and
origin where quotas permit.

Development is available for diagnosis. Validation is available only for a
registered candidate-selection run. Test inputs and gold are held by the human
data owner; the repository records only schema/version, counts, split policy and
cryptographic digests before unsealing.

The custody protocol is:

1. Generate canonical manifests and per-file/case SHA-256 digests.
2. Run schema, privacy, provenance, coverage, duplicate and leakage checks.
3. Freeze development/validation artifacts and record the G3 packet digest.
4. Encrypt or otherwise place test inputs/gold in human-controlled custody;
   publish only counts, schema and bundle digest.
5. Before G6, verify custody and digest equality against G3; record an explicit
   unlock authorization and candidate/evaluator digests.
6. Execute one blinded run; reseal the bundle and preserve all results,
   including failed slices.
7. Any exposure, digest mismatch, unregistered rerun or selective omission
   invalidates the held-out result and requires a new benchmark version or
   explicit gate decision.
