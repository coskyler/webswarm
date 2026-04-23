#!/bin/sh
set -e

if [ "${ENVIRONMENT:-}" = "production" ]; then
  CREDS_JSON="$(aws secretsmanager get-secret-value \
    --region "$AWS_REGION" \
    --secret-id "$DB_CREDENTIALS_SECRET_NAME" \
    --query SecretString \
    --output text)"

  POSTGRES_USER="$(printf '%s' "$CREDS_JSON" | jq -r '.username')"
  POSTGRES_PASSWORD="$(printf '%s' "$CREDS_JSON" | jq -r '.password')"
  POSTGRES_DB="$(printf '%s' "$CREDS_JSON" | jq -r '.dbname')"

  export POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB
fi

printf '"%s" "%s"\n' "$POSTGRES_USER" "$POSTGRES_PASSWORD" > /etc/pgbouncer/userlist.txt

envsubst < /etc/pgbouncer/pgbouncer.ini.template > /etc/pgbouncer/pgbouncer.ini

exec pgbouncer /etc/pgbouncer/pgbouncer.ini