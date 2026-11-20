#!/bin/sh
set -eu

export DB_CONNECTION="$(python -c 'import os; from urllib.parse import quote; password = quote(os.environ["POSTGRES_PASSWORD"], safe=""); print(f"postgresql+psycopg://postgres:{password}@postgres:5432/sakhicare")')"
if [ -z "${SECRET_KEY:-}" ]; then
    key_file=/run/sakhicare/session-key
    if [ ! -s "$key_file" ]; then
        umask 077
        python -c 'import secrets; print(secrets.token_hex(32))' > "$key_file"
    fi
    export SECRET_KEY="$(cat "$key_file")"
fi
exec "$@"
