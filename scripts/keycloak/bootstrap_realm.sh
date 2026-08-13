#!/bin/sh
set -eu

# Run only from an operator-controlled deployment host. Credentials are read
# from the process environment and are never written to the repository.
: "${KEYCLOAK_ADMIN:?bootstrap admin username is required}"
: "${KEYCLOAK_ADMIN_PASSWORD:?bootstrap admin password is required}"
: "${KEYCLOAK_REALM:=projecta}"
: "${KEYCLOAK_URL:=https://auth.example.com}"
: "${KEYCLOAK_REALM_TEMPLATE:=/opt/keycloak/data/import/projecta-realm.json}"

kcadm.sh config credentials --server "$KEYCLOAK_URL" --realm master \
  --user "$KEYCLOAK_ADMIN" --password "$KEYCLOAK_ADMIN_PASSWORD" >/dev/null
kcadm.sh create realms -f "$KEYCLOAK_REALM_TEMPLATE" >/dev/null 2>&1 || \
  kcadm.sh update "realms/$KEYCLOAK_REALM" -f "$KEYCLOAK_REALM_TEMPLATE" >/dev/null

if [ "${KEYCLOAK_RETIRE_BOOTSTRAP_USER_ID:-}" ]; then
  kcadm.sh delete "admin/realms/master/users/$KEYCLOAK_RETIRE_BOOTSTRAP_USER_ID" >/dev/null
fi

unset KEYCLOAK_ADMIN KEYCLOAK_ADMIN_PASSWORD
echo "Realm bootstrap completed; bootstrap authority was retired when an operator user id was supplied."
