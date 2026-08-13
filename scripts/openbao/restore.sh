#!/bin/sh
set -eu
umask 077
: "${OPENBAO_ADDR:=https://openbao:8200}"
: "${OPENBAO_SNAPSHOT_FILE:?encrypted snapshot file is required}"
: "${OPENBAO_SNAPSHOT_HASH_FILE:?snapshot integrity file is required}"
: "${OPENBAO_SNAPSHOT_KEY_FILE:?snapshot encryption key file is required}"
: "${OPENBAO_EXPECTED_CONTRACT_VERSION:?expected snapshot contract version is required}"
: "${OPENBAO_SNAPSHOT_CONTRACT_VERSION:?snapshot contract version is required}"
[ "$OPENBAO_EXPECTED_CONTRACT_VERSION" = "$OPENBAO_SNAPSHOT_CONTRACT_VERSION" ] || { echo "snapshot contract version mismatch" >&2; exit 1; }
sha256sum -c "$OPENBAO_SNAPSHOT_HASH_FILE" >/dev/null
raw="${OPENBAO_SNAPSHOT_FILE%.enc}.raw"
trap 'rm -f "$raw"' EXIT
openssl enc -d -aes-256-cbc -pbkdf2 -in "$OPENBAO_SNAPSHOT_FILE" -out "$raw" -pass file:"$OPENBAO_SNAPSHOT_KEY_FILE"
bao operator raft snapshot restore -address="$OPENBAO_ADDR" "$raw" >/dev/null
echo "OpenBao restore completed; manual unseal and workload re-authentication are still required."
