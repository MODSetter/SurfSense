#!/bin/sh
# ============================================================================
# Electric SQL User Initialization Script (docker-compose only)
# ============================================================================
# This script is ONLY used when running via docker-compose.
#
# How it works:
# - docker-compose.yml mounts this script into the PostgreSQL container's
#   /docker-entrypoint-initdb.d/ directory
# - PostgreSQL automatically executes scripts in that directory on first
#   container initialization
#
# For local PostgreSQL users (non-Docker), this script is NOT used.
# Instead, the Electric user is created by Alembic migration 66
# (66_add_notifications_table_and_electric_replication.py).
#
# Both approaches are idempotent (use IF NOT EXISTS), so running both
# will not cause conflicts.
# ============================================================================

set -e

# Use environment variables with defaults
ELECTRIC_DB_USER="${ELECTRIC_DB_USER:-electric}"
ELECTRIC_DB_PASSWORD="${ELECTRIC_DB_PASSWORD:-electric_password}"

echo "Creating Electric SQL replication user: $ELECTRIC_DB_USER"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_user WHERE usename = '$ELECTRIC_DB_USER') THEN
            CREATE USER $ELECTRIC_DB_USER WITH REPLICATION PASSWORD '$ELECTRIC_DB_PASSWORD';
        END IF;
    END
    \$\$;

    GRANT CONNECT ON DATABASE $POSTGRES_DB TO $ELECTRIC_DB_USER;
    GRANT CREATE ON DATABASE $POSTGRES_DB TO $ELECTRIC_DB_USER;
    GRANT USAGE ON SCHEMA public TO $ELECTRIC_DB_USER;
    GRANT SELECT ON ALL TABLES IN SCHEMA public TO $ELECTRIC_DB_USER;
    GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO $ELECTRIC_DB_USER;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO $ELECTRIC_DB_USER;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON SEQUENCES TO $ELECTRIC_DB_USER;

    -- Create the publication for Electric SQL (if not exists)
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_publication WHERE pubname = 'electric_publication_default') THEN
            CREATE PUBLICATION electric_publication_default;
        END IF;
    END
    \$\$;
EOSQL

echo "Electric SQL user '$ELECTRIC_DB_USER' and publication created successfully"
