#!/bin/sh
set -eu
umask 077
: "${OPENBAO_ADDR:=https://openbao:8200}"
: "${OPENBAO_SNAPSHOT_DIR:?off-host snapshot directory is required}"
: "${OPENBAO_SNAPSHOT_KEY_FILE:?snapshot encryption key file is required}"
: "${OPENBAO_ROOT_TOKEN_FILE:?operator-only root-token file is required}"
mkdir -p "$OPENBAO_SNAPSHOT_DIR"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
raw="$OPENBAO_SNAPSHOT_DIR/.snapshot.$stamp.raw"
encrypted="$OPENBAO_SNAPSHOT_DIR/openbao-$stamp.snap.enc"
export BAO_TOKEN="$(cat "$OPENBAO_ROOT_TOKEN_FILE")"
bao operator raft snapshot save -address="$OPENBAO_ADDR" "$raw" >/dev/null
openssl enc -aes-256-cbc -salt -pbkdf2 -in "$raw" -out "$encrypted" -pass file:"$OPENBAO_SNAPSHOT_KEY_FILE"
rm -f "$raw"
sha256sum "$encrypted" > "$encrypted.sha256"
printf '%s\n' 'OpenBao encrypted snapshot completed; plaintext temporary material was removed.'
unset BAO_TOKEN
