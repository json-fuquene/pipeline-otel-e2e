#!/bin/sh
# Crea o actualiza, de forma idempotente, el rol y el esquema de un servicio.
# Se usa como contenedor de inicialización en Compose (base local existente) y en ECS (Amazon RDS),
# donde el usuario maestro no es superusuario (PostgreSQL 16+: requiere SET sobre el rol).
# Cada servicio solo inicializa su propio rol y esquema.
set -eu

: "${PGHOST:?PGHOST es obligatorio}"
: "${PGUSER:?PGUSER es obligatorio}"
: "${PGPASSWORD:?PGPASSWORD es obligatorio}"
: "${PGDATABASE:?PGDATABASE es obligatorio}"
: "${BOOTSTRAP_ROLE:?BOOTSTRAP_ROLE es obligatorio}"
: "${BOOTSTRAP_SCHEMA:?BOOTSTRAP_SCHEMA es obligatorio}"
: "${BOOTSTRAP_PASSWORD:?BOOTSTRAP_PASSWORD es obligatorio}"

case "$BOOTSTRAP_ROLE$BOOTSTRAP_SCHEMA" in
  *[!a-z_]*) echo "Rol o esquema con caracteres no permitidos." >&2; exit 2 ;;
esac

attempt=1
until psql --set ON_ERROR_STOP=1 --quiet --no-psqlrc <<'SQL'
\getenv role_name BOOTSTRAP_ROLE
\getenv schema_name BOOTSTRAP_SCHEMA
\getenv role_password BOOTSTRAP_PASSWORD
SELECT format('CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT', :'role_name')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'role_name') \gexec
SELECT format('ALTER ROLE %I WITH LOGIN PASSWORD %L', :'role_name', :'role_password') \gexec
SELECT format('GRANT %I TO CURRENT_USER WITH INHERIT FALSE, SET TRUE', :'role_name')
WHERE NOT pg_has_role(CURRENT_USER, :'role_name', 'SET') \gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), :'role_name') \gexec
SELECT format('CREATE SCHEMA IF NOT EXISTS %I AUTHORIZATION %I', :'schema_name', :'role_name') \gexec
SELECT format('SET ROLE %I', :'role_name') \gexec
SELECT format('REVOKE ALL ON SCHEMA %I FROM PUBLIC', :'schema_name') \gexec
RESET ROLE;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
SQL
do
  if [ "$attempt" -ge 5 ]; then
    echo "No fue posible inicializar ${BOOTSTRAP_ROLE} tras ${attempt} intentos." >&2
    exit 1
  fi
  attempt=$((attempt + 1))
  sleep 3
done

echo "{\"event\":\"db_bootstrap_completed\",\"role\":\"${BOOTSTRAP_ROLE}\",\"schema\":\"${BOOTSTRAP_SCHEMA}\"}"
