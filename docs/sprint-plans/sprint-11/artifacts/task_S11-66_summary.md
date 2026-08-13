# S11-66 summary

- Ran `scripts/run_sprint11_clean_compose.ps1 -AllowDirtyWorktree -Start`
  with pinned digests for PostgreSQL, Keycloak 26.7.0, OpenBao 2.6.1, Nginx,
  API, web, and Semantic Core.
- Clean startup reached healthy state for PostgreSQL, Keycloak, OpenBao,
  Semantic Core, API, and web; Fuseki and connector migration/bootstrap exited
  successfully. The public OIDC issuer was served through the TLS edge and the
  static web service started independently so API readiness could validate OIDC
  discovery without a startup cycle.
- Initialized OpenBao with Shamir 3-share/2-threshold, performed the two-share
  manual unseal, configured the bounded AppRole, and ran 24 deterministic
  identity, secret, and Teams journeys.
- Replaced the single-use SecretID, recreated API, proved readiness after
  workload re-authentication, and revoked the bootstrap root token.
- The disposable Compose project and volumes were verified removed after the
  run. The runner now propagates native Compose failures instead of masking
  them.
Validation: all 18 clean-Compose gates passed on 2026-08-13. Evidence:
`s11-66-clean-compose.json`. Stateful cold restore remains the separate S11-63
acceptance gate.
