#!/bin/sh
set -eu

: "${PROJECTA_KEYCLOAK_POSTGRES_DB:?Keycloak database name is required}"
: "${PROJECTA_KEYCLOAK_POSTGRES_USER:?Keycloak database user is required}"
: "${PROJECTA_KEYCLOAK_POSTGRES_PASSWORD:?Keycloak database password is required}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v keycloak_user="$PROJECTA_KEYCLOAK_POSTGRES_USER" \
  -v keycloak_password="$PROJECTA_KEYCLOAK_POSTGRES_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'keycloak_user', :'keycloak_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'keycloak_user')\gexec

SELECT format('ALTER ROLE %I PASSWORD %L', :'keycloak_user', :'keycloak_password')
WHERE EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'keycloak_user')\gexec
SQL

if ! psql -Atqc "SELECT 1 FROM pg_database WHERE datname = '$PROJECTA_KEYCLOAK_POSTGRES_DB'" \
  --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" | grep -q 1; then
  createdb --username "$POSTGRES_USER" --owner "$PROJECTA_KEYCLOAK_POSTGRES_USER" "$PROJECTA_KEYCLOAK_POSTGRES_DB"
fi

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$PROJECTA_KEYCLOAK_POSTGRES_DB" \
  -c "REVOKE ALL ON DATABASE \"$PROJECTA_KEYCLOAK_POSTGRES_DB\" FROM PUBLIC;"
