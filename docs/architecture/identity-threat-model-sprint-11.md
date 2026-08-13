# Identity Threat Model — Sprint 11 S11-07

**Status:** `G1_APPROVED_WITH_REVISIONS`

**Task:** S11-07

## Assets and trust zones

| Asset | Trust zone |
| --- | --- |
| OIDC client secret/bootstrap authority | Operator-only deployment boundary |
| Authorization code, ID token, access token | Short-lived provider/application boundary |
| Session and membership records | Projecta PostgreSQL; server-only |
| Project/capability decisions | Server policy boundary |
| Browser cookie and CSRF state | Browser/edge boundary |
| Keycloak admin, health, metrics | Private management boundary |
| Keycloak authorization, discovery, and JWKS endpoints required by OIDC | Public protocol boundary, limited by the reverse proxy |
| Project/evidence/semantic data | Project-scoped application and data boundaries |

## Threat/control matrix

| ID | Threat | Required control | Evidence |
| --- | --- | --- | --- |
| ID-01 | Login CSRF or unsolicited callback | state, nonce, PKCE, single-use transaction, expiry | Callback negative tests |
| ID-02 | Forged issuer/audience | fixed issuer/audience and exact discovery binding | Token validation tests |
| ID-03 | Algorithm/key confusion | allowlisted algorithms, trusted JWKS, rotation handling | Key rotation tests |
| ID-04 | Authorization-code/token replay | single-use transaction, nonce, expiry, session rotation | Replay tests |
| ID-05 | Session fixation | rotate session after successful login and privilege changes | Session tests |
| ID-06 | Cookie theft | Secure/HttpOnly/SameSite, bounded expiry, revocation | Browser/security tests |
| ID-07 | Missing mutation CSRF defense | CSRF token/origin policy for state-changing browser calls | API/browser tests |
| ID-08 | Open redirect | allowlisted return paths and fixed callback origins | Login tests |
| ID-09 | Stale membership | server lookup/revision before operation and refresh cadence | Membership tests |
| ID-10 | Browser authority injection | strip/ignore actor, role, capability, project, tenant, and trusted headers | Forged-context tests |
| ID-11 | Admin-surface exposure | private admin hostname/path, reverse-proxy deny rules, firewall, no public health/metrics | Compose/edge contract |
| ID-12 | Forwarded-header spoofing | explicit trusted proxy list and overwrite policy | Edge tests |
| ID-13 | Discovery/JWKS outage | readiness/fail-closed behavior with bounded cache policy | Startup/failure tests |
| ID-14 | Cross-project existence leak | project predicates and uniform safe `403`/`404` mapping | Isolation/concurrency tests |
| ID-15 | Provider claim escalation | claims are mapped only to finite identity fields; Projecta membership is authoritative | Policy tests |
| ID-16 | Sensitive audit/log leakage | allowlisted labels and redaction of tokens, claims, codes, and raw IDs | Leak scan |

## Residual risks pending G1/G2

- A single Keycloak instance remains a failure domain.
- Operator-owned TLS, bootstrap, and recovery can be misconfigured.
- Cold recovery restores membership/configuration but invalidates all Projecta
  sessions; users must authenticate again.
- Provider availability and clock skew remain external dependencies.
- A deployment that trusts a proxy incorrectly can reintroduce host and
  forwarded-header confusion.

These risks require explicit acceptance; they are not silently treated as
resolved by adding OIDC code.
