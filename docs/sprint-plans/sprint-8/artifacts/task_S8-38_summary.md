# S8-38 summary

Added multi-project isolation coverage across the catalog and selection
boundary. The API test proves that browser-forged project/actor/secret headers
cannot change the server-owned selection, forged handles are rejected, a
cross-project overview route cannot be used, removed projects clear stale
selection, and no-selection recovery is explicit. Semantic Core query tests
also prove duplicate/out-of-allowlist projects are not added and ordering is
deterministic.
