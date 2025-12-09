#!/bin/bash
set -e

echo "==========================================="
echo "  🏄 SurfSense All-in-One Container"
echo "==========================================="

# Create log directory
mkdir -p /var/log/supervisor

# ================================================
# Initialize PostgreSQL if needed
# ================================================
if [ ! -f /data/postgres/PG_VERSION ]; then
    echo "📦 Initializing PostgreSQL database..."
    
    # Initialize PostgreSQL data directory
    chown -R postgres:postgres /data/postgres
    chmod 700 /data/postgres
    
    su - postgres -c "/usr/lib/postgresql/14/bin/initdb -D /data/postgres"
    
    # Configure PostgreSQL for connections
    echo "host all all 0.0.0.0/0 md5" >> /data/postgres/pg_hba.conf
    echo "local all all trust" >> /data/postgres/pg_hba.conf
    echo "listen_addresses='*'" >> /data/postgres/postgresql.conf
    
    # Start PostgreSQL temporarily to create database and user
    su - postgres -c "/usr/lib/postgresql/14/bin/pg_ctl -D /data/postgres -l /tmp/postgres_init.log start"
    
    # Wait for PostgreSQL to be ready
    sleep 5
    
    # Create user and database
    su - postgres -c "psql -c \"CREATE USER ${POSTGRES_USER:-surfsense} WITH PASSWORD '${POSTGRES_PASSWORD:-surfsense}' SUPERUSER;\""
    su - postgres -c "psql -c \"CREATE DATABASE ${POSTGRES_DB:-surfsense} OWNER ${POSTGRES_USER:-surfsense};\""
    
    # Enable pgvector extension
    su - postgres -c "psql -d ${POSTGRES_DB:-surfsense} -c 'CREATE EXTENSION IF NOT EXISTS vector;'"
    
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
echo "  Backend API:     http://localhost:8000"
echo "  API Docs:        http://localhost:8000/docs"
echo "  Auth Type:       ${AUTH_TYPE:-LOCAL}"
echo "  ETL Service:     ${ETL_SERVICE:-DOCLING}"
echo "==========================================="
echo ""

# ================================================
# Start Supervisor (manages all services)
# ================================================
echo "🚀 Starting all services..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/surfsense.conf

