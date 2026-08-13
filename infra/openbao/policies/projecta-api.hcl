# Service-level custody policy. Projecta enforces exact project, installation,
# connector, provider-tenant, and revision scope before calling this boundary.
path "secret/data/projecta/connector/v1/*" {
  capabilities = ["create", "read", "update", "delete"]
}
path "secret/metadata/projecta/connector/v1/*" {
  capabilities = ["read", "delete"]
}
path "auth/token/lookup-self" {
  capabilities = ["read"]
}
path "sys/health" {
  capabilities = ["read"]
}
