#!/bin/bash
# PostgreSQL initialization script for SurfSense
# This script is called during container startup if the database needs initialization

set -e

PGDATA=${PGDATA:-/data/postgres}
POSTGRES_USER=${POSTGRES_USER:-surfsense}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-surfsense}
POSTGRES_DB=${POSTGRES_DB:-surfsense}

# Electric SQL user credentials (configurable)
ELECTRIC_DB_USER=${ELECTRIC_DB_USER:-electric}
ELECTRIC_DB_PASSWORD=${ELECTRIC_DB_PASSWORD:-electric_password}

echo "Initializing PostgreSQL..."

# Check if PostgreSQL is already initialized
if [ -f "$PGDATA/PG_VERSION" ]; then
    echo "PostgreSQL data directory already exists. Skipping initialization."
    exit 0
fi

# Initialize the database cluster
/usr/lib/postgresql/14/bin/initdb -D "$PGDATA" --username=postgres

# Configure PostgreSQL
cat >> "$PGDATA/postgresql.conf" << EOF
listen_addresses = '*'
max_connections = 200
shared_buffers = 256MB

# Enable logical replication (required for Electric SQL)
wal_level = logical
max_replication_slots = 10
max_wal_senders = 10

# Performance settings
checkpoint_timeout = 10min
max_wal_size = 1GB
min_wal_size = 80MB
EOF

cat >> "$PGDATA/pg_hba.conf" << EOF
# Allow connections from anywhere with password
host all all 0.0.0.0/0 md5
host all all ::0/0 md5
EOF

# Start PostgreSQL temporarily
/usr/lib/postgresql/14/bin/pg_ctl -D "$PGDATA" -l /tmp/postgres_init.log start

# Wait for PostgreSQL to start
sleep 3

# Create user and database
psql -U postgres << EOF
CREATE USER $POSTGRES_USER WITH PASSWORD '$POSTGRES_PASSWORD' SUPERUSER;
CREATE DATABASE $POSTGRES_DB OWNER $POSTGRES_USER;
\c $POSTGRES_DB
CREATE EXTENSION IF NOT EXISTS vector;

-- Create Electric SQL replication user
CREATE USER $ELECTRIC_DB_USER WITH REPLICATION PASSWORD '$ELECTRIC_DB_PASSWORD';
GRANT CONNECT ON DATABASE $POSTGRES_DB TO $ELECTRIC_DB_USER;
GRANT USAGE ON SCHEMA public TO $ELECTRIC_DB_USER;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO $ELECTRIC_DB_USER;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO $ELECTRIC_DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO $ELECTRIC_DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON SEQUENCES TO $ELECTRIC_DB_USER;
EOF

echo "PostgreSQL initialized successfully."

# Stop PostgreSQL (supervisor will start it)
/usr/lib/postgresql/14/bin/pg_ctl -D "$PGDATA" stop

