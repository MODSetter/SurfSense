#!/bin/bash
set -e

echo "==========================================="
echo "  🏄 SurfSense All-in-One Container"
echo "==========================================="

# Create log directory
mkdir -p /var/log/supervisor

# ================================================
# Ensure data directory exists
# ================================================
mkdir -p /data

# ================================================
# Generate SECRET_KEY if not provided
# ================================================
if [ -z "$SECRET_KEY" ]; then
    # Generate a random secret key and persist it
    if [ -f /data/.secret_key ]; then
        export SECRET_KEY=$(cat /data/.secret_key)
        echo "✅ Using existing SECRET_KEY from persistent storage"
    else
        export SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
        echo "$SECRET_KEY" > /data/.secret_key
        chmod 600 /data/.secret_key
        echo "✅ Generated new SECRET_KEY (saved for persistence)"
    fi
fi

# ================================================
# Set default TTS/STT services if not provided
# ================================================
if [ -z "$TTS_SERVICE" ]; then
    export TTS_SERVICE="local/kokoro"
    echo "✅ Using default TTS_SERVICE: local/kokoro"
fi

if [ -z "$STT_SERVICE" ]; then
    export STT_SERVICE="local/base"
    echo "✅ Using default STT_SERVICE: local/base"
fi

# ================================================
# Set Electric SQL configuration
# ================================================
export ELECTRIC_DB_USER="${ELECTRIC_DB_USER:-electric}"
export ELECTRIC_DB_PASSWORD="${ELECTRIC_DB_PASSWORD:-electric_password}"
if [ -z "$ELECTRIC_DATABASE_URL" ]; then
    export ELECTRIC_DATABASE_URL="postgresql://${ELECTRIC_DB_USER}:${ELECTRIC_DB_PASSWORD}@localhost:5432/${POSTGRES_DB:-surfsense}?sslmode=disable"
    echo "✅ Electric SQL URL configured dynamically"
else
    # Ensure sslmode=disable is in the URL if not already present
    if [[ "$ELECTRIC_DATABASE_URL" != *"sslmode="* ]]; then
        # Add sslmode=disable (handle both cases: with or without existing query params)
        if [[ "$ELECTRIC_DATABASE_URL" == *"?"* ]]; then
            export ELECTRIC_DATABASE_URL="${ELECTRIC_DATABASE_URL}&sslmode=disable"
        else
            export ELECTRIC_DATABASE_URL="${ELECTRIC_DATABASE_URL}?sslmode=disable"
        fi
    fi
    echo "✅ Electric SQL URL configured from environment"
fi

# Set Electric SQL port
export ELECTRIC_PORT="${ELECTRIC_PORT:-5133}"
export PORT="${ELECTRIC_PORT}"

# ================================================
# Initialize PostgreSQL if needed
# ================================================
if [ ! -f /data/postgres/PG_VERSION ]; then
    echo "📦 Initializing PostgreSQL database..."
    
    # Initialize PostgreSQL data directory
    chown -R postgres:postgres /data/postgres
    chmod 700 /data/postgres
    
    # Initialize with UTF8 encoding (required for proper text handling)
    su - postgres -c "/usr/lib/postgresql/14/bin/initdb -D /data/postgres --encoding=UTF8 --locale=C.UTF-8"
    
    # Configure PostgreSQL for connections
    echo "host all all 0.0.0.0/0 md5" >> /data/postgres/pg_hba.conf
    echo "local all all trust" >> /data/postgres/pg_hba.conf
    echo "listen_addresses='*'" >> /data/postgres/postgresql.conf
    
    # Enable logical replication for Electric SQL
    echo "wal_level = logical" >> /data/postgres/postgresql.conf
    echo "max_replication_slots = 10" >> /data/postgres/postgresql.conf
    echo "max_wal_senders = 10" >> /data/postgres/postgresql.conf
    
    # Start PostgreSQL temporarily to create database and user
    su - postgres -c "/usr/lib/postgresql/14/bin/pg_ctl -D /data/postgres -l /tmp/postgres_init.log start"
    
    # Wait for PostgreSQL to be ready
    sleep 5
    
    # Create user and database
    su - postgres -c "psql -c \"CREATE USER ${POSTGRES_USER:-surfsense} WITH PASSWORD '${POSTGRES_PASSWORD:-surfsense}' SUPERUSER;\""
    su - postgres -c "psql -c \"CREATE DATABASE ${POSTGRES_DB:-surfsense} OWNER ${POSTGRES_USER:-surfsense};\""
    
    # Enable pgvector extension
    su - postgres -c "psql -d ${POSTGRES_DB:-surfsense} -c 'CREATE EXTENSION IF NOT EXISTS vector;'"
    
    # Create Electric SQL replication user (idempotent - uses IF NOT EXISTS)
    echo "📡 Creating Electric SQL replication user..."
    su - postgres -c "psql -d ${POSTGRES_DB:-surfsense} <<-EOSQL
        DO \\\$\\\$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_user WHERE usename = '${ELECTRIC_DB_USER}') THEN
                CREATE USER ${ELECTRIC_DB_USER} WITH REPLICATION PASSWORD '${ELECTRIC_DB_PASSWORD}';
            END IF;
        END
        \\\$\\\$;

        GRANT CONNECT ON DATABASE ${POSTGRES_DB:-surfsense} TO ${ELECTRIC_DB_USER};
        GRANT USAGE ON SCHEMA public TO ${ELECTRIC_DB_USER};
        GRANT SELECT ON ALL TABLES IN SCHEMA public TO ${ELECTRIC_DB_USER};
        GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO ${ELECTRIC_DB_USER};
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO ${ELECTRIC_DB_USER};
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON SEQUENCES TO ${ELECTRIC_DB_USER};

        -- Create the publication for Electric SQL (if not exists)
        DO \\\$\\\$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_publication WHERE pubname = 'electric_publication_default') THEN
                CREATE PUBLICATION electric_publication_default;
            END IF;
        END
        \\\$\\\$;
EOSQL"
    echo "✅ Electric SQL user '${ELECTRIC_DB_USER}' created"
    
    # Stop temporary PostgreSQL
    su - postgres -c "/usr/lib/postgresql/14/bin/pg_ctl -D /data/postgres stop"
    
    echo "✅ PostgreSQL initialized successfully"
else
    echo "✅ PostgreSQL data directory already exists"
fi

# ================================================
# Initialize Redis data directory
# ================================================
mkdir -p /data/redis
chmod 755 /data/redis
echo "✅ Redis data directory ready"

# ================================================
# Copy frontend build to runtime location
# ================================================
if [ -d /app/frontend/.next/standalone ]; then
    cp -r /app/frontend/.next/standalone/* /app/frontend/ 2>/dev/null || true
    cp -r /app/frontend/.next/static /app/frontend/.next/static 2>/dev/null || true
fi

# ================================================
# Runtime Environment Variable Replacement
# ================================================
# Next.js NEXT_PUBLIC_* vars are baked in at build time.
# This replaces placeholder values with actual runtime env vars.
echo "🔧 Applying runtime environment configuration..."

# Set defaults if not provided
NEXT_PUBLIC_FASTAPI_BACKEND_URL="${NEXT_PUBLIC_FASTAPI_BACKEND_URL:-http://localhost:8000}"
NEXT_PUBLIC_FASTAPI_BACKEND_AUTH_TYPE="${NEXT_PUBLIC_FASTAPI_BACKEND_AUTH_TYPE:-LOCAL}"
NEXT_PUBLIC_ETL_SERVICE="${NEXT_PUBLIC_ETL_SERVICE:-DOCLING}"
NEXT_PUBLIC_ELECTRIC_URL="${NEXT_PUBLIC_ELECTRIC_URL:-http://localhost:5133}"
NEXT_PUBLIC_ELECTRIC_AUTH_MODE="${NEXT_PUBLIC_ELECTRIC_AUTH_MODE:-insecure}"

# Replace placeholders in all JS files
find /app/frontend -type f \( -name "*.js" -o -name "*.json" \) -exec sed -i \
    -e "s|__NEXT_PUBLIC_FASTAPI_BACKEND_URL__|${NEXT_PUBLIC_FASTAPI_BACKEND_URL}|g" \
    -e "s|__NEXT_PUBLIC_FASTAPI_BACKEND_AUTH_TYPE__|${NEXT_PUBLIC_FASTAPI_BACKEND_AUTH_TYPE}|g" \
    -e "s|__NEXT_PUBLIC_ETL_SERVICE__|${NEXT_PUBLIC_ETL_SERVICE}|g" \
    -e "s|__NEXT_PUBLIC_ELECTRIC_URL__|${NEXT_PUBLIC_ELECTRIC_URL}|g" \
    -e "s|__NEXT_PUBLIC_ELECTRIC_AUTH_MODE__|${NEXT_PUBLIC_ELECTRIC_AUTH_MODE}|g" \
    {} +

echo "✅ Environment configuration applied"
echo "   Backend URL:   ${NEXT_PUBLIC_FASTAPI_BACKEND_URL}"
echo "   Auth Type:     ${NEXT_PUBLIC_FASTAPI_BACKEND_AUTH_TYPE}"
echo "   ETL Service:   ${NEXT_PUBLIC_ETL_SERVICE}"
echo "   Electric URL:  ${NEXT_PUBLIC_ELECTRIC_URL}"

# ================================================
# Run database migrations
# ================================================
run_migrations() {
    echo "🔄 Running database migrations..."
    
    # Start PostgreSQL temporarily for migrations
    su - postgres -c "/usr/lib/postgresql/14/bin/pg_ctl -D /data/postgres -l /tmp/postgres_migrate.log start"
    sleep 5
    
    # Start Redis temporarily for migrations (some might need it)
    redis-server --dir /data/redis --daemonize yes
    sleep 2
    
    # Run alembic migrations
    cd /app/backend
    alembic upgrade head || echo "⚠️ Migrations may have already been applied"
    
    # Stop temporary services
    redis-cli shutdown || true
    su - postgres -c "/usr/lib/postgresql/14/bin/pg_ctl -D /data/postgres stop"
    
    echo "✅ Database migrations complete"
}

# Run migrations on first start or when explicitly requested
if [ ! -f /data/.migrations_run ] || [ "${FORCE_MIGRATIONS:-false}" = "true" ]; then
    run_migrations
    touch /data/.migrations_run
fi

# ================================================
# Environment Variables Info
# ================================================
echo ""
echo "==========================================="
echo "  📋 Configuration"
echo "==========================================="
echo "  Frontend URL:    http://localhost:3000"
echo "  Backend API:     ${NEXT_PUBLIC_FASTAPI_BACKEND_URL}"
echo "  API Docs:        ${NEXT_PUBLIC_FASTAPI_BACKEND_URL}/docs"
echo "  Electric URL:    ${NEXT_PUBLIC_ELECTRIC_URL:-http://localhost:5133}"
echo "  Auth Type:       ${NEXT_PUBLIC_FASTAPI_BACKEND_AUTH_TYPE}"
echo "  ETL Service:     ${NEXT_PUBLIC_ETL_SERVICE}"
echo "  TTS Service:     ${TTS_SERVICE}"
echo "  STT Service:     ${STT_SERVICE}"
echo "==========================================="
echo ""

# ================================================
# Start Supervisor (manages all services)
# ================================================
echo "🚀 Starting all services..."
exec /usr/local/bin/supervisord -c /etc/supervisor/conf.d/surfsense.conf

