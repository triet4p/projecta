# M3 Extraction Error Taxonomy

**Status:** IMPLEMENTATION_BASELINE
**Task:** S5-02

Every extraction failure is normalized to one stable error class before it
crosses the gateway, application, or Semantic Core boundary. Error responses
contain a code, safe human detail, retryability, and correlation ID. They do
not contain note text, provider payloads, credentials, prompts, stack traces,
graph IRIs, or cross-project identifiers.

| Class | Code | Meaning | Retry | Persistence |
|---|---|---|---|---|
| `schema_invalid` | `EXTRACTION_SCHEMA_INVALID` | Gateway output cannot be parsed or violates the versioned JSON/Pydantic contract. | No | None |
| `unsupported_type` | `EXTRACTION_UNSUPPORTED_TYPE` | Entity type is absent from the approved class allowlist. | No | None |
| `unsupported_relation` | `EXTRACTION_UNSUPPORTED_RELATION` | Predicate is absent from the approved relation allowlist or its endpoints are invalid. | No | None |
| `invalid_evidence` | `EXTRACTION_INVALID_EVIDENCE` | Span is empty/out of bounds/overlapping or recomputed text does not match source text. | No | None |
| `hallucinated_link` | `EXTRACTION_LINK_NOT_BOUNDED` | Proposed target is not in the server-provided bounded entity context. | No | None |
| `cross_project_link` | `EXTRACTION_CROSS_PROJECT_LINK` | Target belongs to another project or cannot be proven to belong to the trusted project. | No | None |
| `abstention` | `EXTRACTION_ABSTAINED` | Model intentionally returns no proposal because evidence is insufficient or ambiguous. | No | A successful empty result may record the abstention activity; no candidate |
| `timeout` | `EXTRACTION_TIMEOUT` | Provider or gateway exceeded the configured deadline. | Bounded retry only | None |
| `rate_limit` | `EXTRACTION_RATE_LIMITED` | Provider refused the request due to quota or rate limit. | Retry after bounded backoff if allowed | None |
| `provider_failure` | `EXTRACTION_PROVIDER_FAILURE` | Provider SDK/network/service failed without a more specific class. | Bounded retry only | None |
| `configuration_invalid` | `EXTRACTION_CONFIGURATION_INVALID` | Required model or credential configuration is missing or malformed. | No | None |
| `normalization_invalid` | `EXTRACTION_NORMALIZATION_INVALID` | A structurally valid response becomes invalid after canonicalization, deduplication, or allowlist checks. | No | None |
| `semantic_validation_failed` | `CANDIDATE_INVALID` | Candidate batch fails approved SHACL/domain validation. | No | Transaction rollback |
| `project_context_required` | `PROJECT_CONTEXT_REQUIRED` | Trusted project/actor/request context is missing or invalid. | No | None |
| `idempotency_conflict` | `IDEMPOTENCY_KEY_REUSED` | Key is reused for a different canonical operation. | No | None |
| `semantic_unavailable` | `SEMANTIC_CONTRACT_UNAVAILABLE` | Semantic Core is unreachable or returns an invalid finite contract. | Bounded client retry only | None |
| `internal_failure` | `INTERNAL_ERROR` | Unexpected failure after safe classification. | No automatic retry unless explicitly configured | Transaction rollback |

## Classification Rules

Schema, allowlist, evidence, link, normalization, and semantic-validation
errors fail closed and never create partial source/candidate/provenance data.
An abstention is not an error from the caller's perspective: it returns a
successful zero-candidate result and records only safe activity metadata.

Timeout, rate-limit, and provider failures may be retried within one bounded
request deadline. Retry policy must not log or expose the raw request. If all
attempts fail, the final normalized class is returned and no semantic mutation
is attempted.

Missing configuration is fail-closed and non-retryable. A model cannot choose
an ontology class, predicate, graph, target ID, or policy outcome outside the
server allowlists. Unknown or malformed error payloads map to the nearest safe
class and ultimately `INTERNAL_ERROR`.

## Public Boundary Mapping

FastAPI preserves the existing public problem envelope and maps the taxonomy
as follows: context or malformed caller input → `401 PROJECT_CONTEXT_REQUIRED`
or `400 INVALID_REQUEST`; invalid provider schema, evidence, allowlist, link,
normalization, configuration, timeout, rate-limit, or provider failure →
`503 SEMANTIC_CONTRACT_UNAVAILABLE` (with a stable extraction code in the
private normalized event); semantic validation → `422 CANDIDATE_INVALID`;
idempotency → `409 IDEMPOTENCY_KEY_REUSED`; provider timeout/rate-limit/failure
and Core outage → `503 SEMANTIC_CONTRACT_UNAVAILABLE`; unexpected failures →
`500 INTERNAL_ERROR`. Exact provider-specific status and payload details never
leave the private gateway boundary.

## Safety Invariants

- No classified error can mutate asserted or inferred graphs.
- A failed batch cannot leave only some entities, relations, links, or provenance.
- Cross-project or fabricated links are distinguishable from ordinary invalid links for audit and metrics.
- Retryability is explicit and bounded; there is no unbounded retry loop.
- Error telemetry records class, versions, latency, attempt count, and request ID, but redacts source and provider payloads.
