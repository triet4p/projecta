# Teams Connector Threat Model — Sprint 11 S11-12

**Status:** `G1_APPROVED_WITH_REVISIONS`

**Task:** S11-12

## Threat/control matrix

| ID | Threat | Required control |
| --- | --- | --- |
| TM-01 | Consent escalation or overprivileged app | least-privilege permission review; RSC/app choice recorded; no broader scope than one approved channel/tenant |
| TM-02 | Cross-tenant confusion | installation binds tenant/team/channel; token and payload identity must match the binding |
| TM-03 | SSRF through configuration or payload | fixed HTTPS host, allowlisted path, no redirects, no arbitrary URL fetch |
| TM-04 | Malicious `@odata.nextLink` | parse and validate scheme/host/path/query size before every follow |
| TM-05 | HTML/script/content injection | treat body and hosted content as untrusted; normalize to bounded evidence representation |
| TM-06 | Oversized message/reply/attachment | byte, item, page, reply, and deadline bounds before storage |
| TM-07 | External identifier disclosure | keep provider IDs internal; expose opaque Projecta handles only |
| TM-08 | Access-token or secret disclosure | server-only secret snapshot; redaction in exceptions/logs/telemetry/artifacts |
| TM-09 | Throttling abuse | map `429` to finite terminal outcome; no hidden retry or cursor movement |
| TM-10 | Edit/delete ambiguity | deterministic event identity and explicit update/deletion observation semantics |
| TM-11 | Malformed provider payload | strict typed validation, bounded errors, rollback before cursor commit |
| TM-12 | Partial pagination treated as complete | explicit truncation status; no unqualified success |
| TM-13 | Provider response ordering changes | watermark based on documented modified ordering; replay/idempotency tests |
| TM-14 | Cancellation/process interruption | cooperative cancellation, transactional completion, unchanged cursor on incomplete work |
| TM-15 | Identity/display-name merge | actor hint is non-authoritative; no automatic Person merge |
| TM-16 | Evidence/raw payload leakage | content-addressed bounded evidence, safe public projection, leak scan across logs/DB/RDF/UI |

## Trust boundaries

```text
Projecta browser
  → typed API + server policy
  → Teams installation + scoped SecretStore snapshot
  → fixed Graph HTTPS boundary
  → normalized canonical event/evidence
  → existing candidate/confirmation lifecycle
```

The connector never receives browser authority, writes asserted RDF, or
decides project membership. The provider is an untrusted source of evidence,
not Projecta domain truth.

## Required negative evidence

Replay fixtures and tests must cover invalid consent, `401`, `403`, `429`,
timeouts, malformed JSON, hostile HTML, invalid next links, oversized content,
duplicate/edit/delete events, partial pages, cancellation, restart, and
cross-tenant/project installation confusion.

## Residual risks

- Microsoft Graph endpoint/permission behavior can change and requires a
  pre-implementation re-check.
- Resource-specific consent and tenant administrator ownership remain external
  operational dependencies.
- Provider-side deletion/history semantics may limit exact reconstruction;
  the adapter must report bounded uncertainty rather than inventing state.
