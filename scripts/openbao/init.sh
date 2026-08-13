#!/bin/sh
set -eu
umask 077

: "${OPENBAO_ADDR:=https://openbao:8200}"
: "${OPENBAO_RECOVERY_DIR:?offline recovery directory is required}"
: "${OPENBAO_ROOT_TOKEN_FILE:?operator-only root-token file is required}"
command -v jq >/dev/null 2>&1 || { echo "jq is required on the operator host" >&2; exit 1; }

case "$OPENBAO_RECOVERY_DIR" in
  ./*|*projecta*repo*|*git*) echo "recovery directory must be outside the repository" >&2; exit 1 ;;
esac
mkdir -p "$OPENBAO_RECOVERY_DIR"
if [ -s "$OPENBAO_ROOT_TOKEN_FILE" ] && [ -s "$OPENBAO_RECOVERY_DIR/share-1" ] && [ -s "$OPENBAO_RECOVERY_DIR/share-2" ] && [ -s "$OPENBAO_RECOVERY_DIR/share-3" ]; then
  echo "OpenBao is already initialized; existing recovery material was not changed."
  exit 0
fi
if [ -s "$OPENBAO_ROOT_TOKEN_FILE" ] || [ -s "$OPENBAO_RECOVERY_DIR/share-1" ] || [ -s "$OPENBAO_RECOVERY_DIR/share-2" ] || [ -s "$OPENBAO_RECOVERY_DIR/share-3" ]; then
  echo "partial OpenBao initialization material exists; refusing to overwrite" >&2
  exit 1
fi

tmp="$OPENBAO_RECOVERY_DIR/.init.$$.json"
trap 'rm -f "$tmp"' EXIT
bao operator init -address="$OPENBAO_ADDR" -key-shares=3 -key-threshold=2 -format=json > "$tmp"
jq -er '.root_token' "$tmp" > "$OPENBAO_ROOT_TOKEN_FILE"
jq -er '.unseal_keys_b64[0]' "$tmp" > "$OPENBAO_RECOVERY_DIR/share-1"
jq -er '.unseal_keys_b64[1]' "$tmp" > "$OPENBAO_RECOVERY_DIR/share-2"
jq -er '.unseal_keys_b64[2]' "$tmp" > "$OPENBAO_RECOVERY_DIR/share-3"
chmod 600 "$OPENBAO_ROOT_TOKEN_FILE" "$OPENBAO_RECOVERY_DIR"/share-*
echo "OpenBao initialized; recovery material was written to operator custody only. Values were not printed."
