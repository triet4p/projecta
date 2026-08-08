# Experience-Mode Context Threat Model — Sprint 7

**Status:** PROPOSED — pending S7-07 architecture/security review
**Task:** S7-05

## Objective and Boundary

Sprint 7 needs a local web experience that can exercise a known Projecta
project without turning browser input into trusted production identity. The
experience adapter is a deployment convenience for a local profile, not an
authentication provider, authorization system, or tenant-management feature.

The trusted values are:

- `projectId`: the fixed or explicitly allowlisted project served by the local profile;
- `actorId`: the fixed or allowlisted local actor;
- `requestId`: a server-generated or deployment-established correlation ID;
- the context-injection mechanism and any deployment secret used between trusted services.

The browser is untrusted with respect to all four values and must never receive
the deployment secret.

## Assets and Trust Boundaries

| Asset/boundary | Trusted party | Threat if crossed |
|---|---|---|
| Browser SPA | User agent and local user; untrusted input | Can forge headers, alter JavaScript state, replay requests, or inspect responses. |
| Same-origin web/API boundary | Local reverse proxy or Application API adapter | Can accidentally forward browser-selected identity or expose private routes. |
| Application API context | Server-side adapter and FastAPI dependency | Routes all project data and Semantic Core calls; compromise becomes cross-project risk. |
| Semantic Core private boundary | Application API to Java/Javalin service | Must receive only server-established context, never browser identity or arbitrary graph operations. |
| Context secret | Deployment/service boundary only | Disclosure permits spoofing of trusted context if project/actor headers are accepted. |
| LLM settings/secret boundary | Server-side configuration and approved secret store | Disclosure permits provider use, cost, data exfiltration, or credential reuse. |

The required request path is:

```text
Browser
  → same-origin web/API boundary
  → server-established local context
  → FastAPI Application API
  → private Semantic Core boundary
  → project-scoped RDF operations
```

The browser must not call Semantic Core or Fuseki directly. A direct browser
call to the current header-plus-secret implementation is not an acceptable
production shape because a browser can set arbitrary `X-Projecta-*` headers.

## Threats and Controls

| Threat | Example | Required control | Evidence |
|---|---|---|---|
| Project override | User changes `projectId` in browser devtools and reads another project. | Local adapter owns a fixed/allowlisted project; strips browser context headers; injects context server-side. | Negative request test; cross-project API test. |
| Actor spoofing | User changes `actorId` to impersonate a reviewer. | Actor is deployment-established; browser cannot choose reviewer/actor ID. | Confirmation/rejection actor evidence and header-stripping test. |
| Context-secret exfiltration | Secret appears in bundle, DOM, request, error, or browser storage. | Secret stays in server/deployment boundary; same-origin proxy injects private metadata after browser request. | Bundle, DOM, network, storage, log, and telemetry scans. |
| Direct private-service access | Browser calls Semantic Core/Fuseki or discovers internal URL. | Do not publish private ports in the web profile; Application API is the only client contract. | Compose/network test and forbidden-origin check. |
| Origin abuse | Another local website sends state-changing requests to the API. | Same-origin delivery, restrictive bind/origin policy, no permissive CORS, and explicit CSRF strategy if browser credentials are introduced. | Cross-origin request test. |
| Local network exposure | API/web binds to all interfaces and another machine uses local context. | Local profile binds to loopback by default; any non-loopback bind requires an explicit deployment setting and fails closed without an approved auth boundary. | Compose bind inspection and startup negative test. |
| Production profile misuse | Local fixed context is enabled in early production. | `experience profile=local` is explicit; production/default profile disables the adapter and refuses startup or project-scoped requests. | Production Compose/config negative test. |
| Header/proxy confusion | Proxy forwards user-supplied trusted headers instead of replacing them. | Strip `X-Projecta-Project-Id`, `X-Projecta-Actor-Id`, `X-Projecta-Context-Secret`, and `X-Request-Id` from public input before injection. | Proxy/API integration test. |
| Replay/double mutation | Browser retry creates duplicate capture or decision. | Preserve released idempotency keys; disable duplicate submit; surface `200` replay and `409` conflict distinctly. | M2/M3 lifecycle E2E and client tests. |
| Error/data leakage | 401/404/409/500 responses reveal another project, graph name, or stack trace. | Keep sanitized RFC 7807 boundary and project-scoped not-found semantics. | Problem-response regression tests. |
| Request forgery from compromised UI | XSS or malicious extension submits valid same-origin operations. | Treat browser as untrusted; enforce server-side context, bounded routes, input validation, CSP/security headers, and future auth seam. | Security review and browser security checks. |
| Operational mutation abuse | Ordinary screen exposes inference rebuild as unrestricted admin action. | Gate rebuild behind local experience mode and a clearly labeled diagnostics capability; hide/disable it outside that mode. | Production-disabled UI/API test. |

## Local Experience Profile

The proposed local profile has these properties:

- The web and Application API are served from one documented same-origin entry
  point, preferably bound to loopback.
- The profile supplies one fixed or allowlisted project and actor through a
  server-side adapter. The browser receives display-safe context metadata only.
- Public requests cannot select or override project, actor, reviewer, graph,
  tenant, or deployment secret.
- The adapter is explicitly disabled when a production/early-production
  profile is selected; there is no silent fallback to local identity.
- The profile is suitable for deterministic local Compose and browser E2E only.
  It is not evidence of production authentication or authorization.

## Abuse Cases Outside This Sprint

Authentication, RBAC/ABAC, tenant administration, remote user identity,
connector credentials, public internet exposure, and production secret-manager
integration require a later reviewed security boundary. Sprint 7 may create
interfaces for these concerns but must not claim that the local adapter solves
them.

## Review Gates

S7-07 must approve the local profile, bind/origin policy, header-stripping
location, production-disable behavior, and explicit non-goals before S7-24 or
frontend integration is frozen.
