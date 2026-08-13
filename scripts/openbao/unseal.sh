#!/bin/sh
set -eu
: "${OPENBAO_ADDR:=https://openbao:8200}"
: "${OPENBAO_RECOVERY_DIR:?offline recovery directory is required}"
for share in 1 2; do
  file="$OPENBAO_RECOVERY_DIR/share-$share"
  test -s "$file" || { echo "missing recovery share" >&2; exit 1; }
  bao operator unseal -address="$OPENBAO_ADDR" "$(cat "$file")" >/dev/null
done
echo "OpenBao unseal quorum submitted; status only was reported."
