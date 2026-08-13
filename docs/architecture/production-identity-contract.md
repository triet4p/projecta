# Production Identity Contract — Sprint 11 S11-05

**Status:** `G1_APPROVED_WITH_REVISIONS`

**Task:** S11-05

**Contract:** `projecta-identity.v1-draft`

## Authority

Projecta creates the durable authorization context. An OIDC token is an
authentication input, not a durable Projecta grant. The server validates the
provider response, creates an opaque session, resolves membership, and then
constructs the existing `ConnectorPrincipal`.

## Provider configuration

Production configuration must explicitly provide:

- fixed issuer URL and discovery URL derived from that issuer;
- client ID and redirect URI allowlist;
- allowed audience/client identifier and accepted signing algorithms;
- JWKS cache limits and key-rotation behavior;
- clock-skew allowance and session lifetime;
- public login hostname and private management/readiness endpoints.

Missing, conflicting, dynamic, or malformed values fail closed at startup or
at the first protected operation according to the selected readiness policy.

## Login initiation

The server creates a bounded login transaction containing:

- cryptographically random state;
- nonce;
- PKCE verifier/challenge using S256;
- correlation/request ID;
- allowlisted return path;
- creation and expiry time;
- browser/session binding as appropriate for the selected cookie strategy.

The transaction is stored server-side. The browser receives no provider
credential, refresh token, authorization authority, or unbounded return URL.

## Callback validation order

Before creating a session, Projecta must validate:

1. callback transaction exists, is unexpired, and matches the browser binding;
2. state, code, and PKCE verifier are valid and single-use;
3. token issuer exactly matches configured issuer;
4. signature and algorithm validate against the trusted JWKS set;
5. audience/client binding is valid;
6. `exp`, `iat`, and any required `nbf` pass bounded clock-skew rules;
7. subject and finite claim mappings are non-empty and structurally valid;
8. no unsupported claim is used as a Projecta role, project, or capability.

Any failure produces a safe finite login problem and no durable session.

## Server session

The session repository stores an opaque session identifier and server-owned
fields such as provider subject, issuer, internal actor mapping, tenant scope,
creation/last-seen/expiry times, revocation state, and safe audit attribution.
Raw ID tokens, access tokens, provider claims, and secret values are not
stored in browser state or public DTOs. A refresh-token design, if required by
the selected Teams flow, needs a separate scoped storage decision.

After cold recovery, Projecta restores user mapping and membership data but
increments a session epoch or otherwise revokes every Projecta session. No
browser login is restored; users must complete OIDC login again.

## Principal and policy resolution

Each protected request resolves:

```text
opaque session
→ active session and expiry
→ internal actor/tenant mapping
→ server-owned project membership
→ finite role/capability set
→ connector operation and installation revision
```

The adapter strips or ignores browser-supplied actor, role, capability,
project, tenant, trusted-context, graph, and secret headers. Existing safe
`401`, `403`, `404`, and stale `409` behavior is preserved.

## Cookies, CSRF, logout, and expiry

- Session cookies are `Secure`, `HttpOnly`, and use an explicit `SameSite`
  policy suitable for the chosen OIDC flow.
- Session identifiers rotate after login and on the selected reauthentication
  events.
- All browser mutations require a CSRF defense; OIDC state/nonce/PKCE do not
  replace mutation CSRF protection.
- Logout revokes the local session and clears the browser cookie. Provider
  logout is used only if approved by the selected provider contract.
- Expired, revoked, stale, or membership-removed sessions fail closed and do
  not fall back to local experience context.

## Safe errors and audit

Public responses expose only bounded problem codes, safe detail, and request
ID. Logs and audit contain correlation, safe action class, provider-safe
subject reference, and outcome class; never raw tokens, claims, tenant IDs,
authorization codes, or redirect values.

## Compatibility and test obligations

The contract must prove wrong issuer/audience, signature/key rotation,
state/nonce/PKCE, clock skew, cookie/CSRF, logout/expiry/revocation, stale
membership, cross-project access, and production local-adapter rejection.

This draft does not select a provider version or approve G1.
