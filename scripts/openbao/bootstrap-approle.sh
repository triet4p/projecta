#!/bin/sh
set -eu
umask 077
: "${OPENBAO_ADDR:=https://openbao:8200}"
: "${OPENBAO_ROOT_TOKEN_FILE:?operator-only root-token file is required}"
: "${OPENBAO_ROLE_ID_FILE:?restricted RoleID output file is required}"
: "${OPENBAO_SECRET_ID_FILE:?restricted SecretID output file is required}"
: "${OPENBAO_POLICY_FILE:=/policies/projecta-api.hcl}"

root_token="$(cat "$OPENBAO_ROOT_TOKEN_FILE")"
export BAO_TOKEN="$root_token"
bao policy write -address="$OPENBAO_ADDR" projecta-api "$OPENBAO_POLICY_FILE" >/dev/null
bao auth enable -address="$OPENBAO_ADDR" approle >/dev/null 2>&1 || true
bao write -address="$OPENBAO_ADDR" auth/approle/role/projecta-api \
  token_policies=projecta-api token_ttl=15m token_max_ttl=60m \
  secret_id_ttl=10m secret_id_num_uses=1 >/dev/null
bao read -address="$OPENBAO_ADDR" -field=role_id auth/approle/role/projecta-api/role-id > "$OPENBAO_ROLE_ID_FILE"
bao write -address="$OPENBAO_ADDR" -field=secret_id auth/approle/role/projecta-api/secret-id > "$OPENBAO_SECRET_ID_FILE"
chmod 600 "$OPENBAO_ROLE_ID_FILE" "$OPENBAO_SECRET_ID_FILE"
bao token revoke -address="$OPENBAO_ADDR" -self >/dev/null
unset BAO_TOKEN root_token
echo "OpenBao AppRole bootstrap completed; RoleID/SecretID were written to restricted transport files."
