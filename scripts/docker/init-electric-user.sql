-- Create Electric SQL replication user
-- This script is run during PostgreSQL initialization

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'electric') THEN
        CREATE USER electric WITH REPLICATION PASSWORD 'electric_password';
    END IF;
END
$$;

-- Grant necessary permissions
GRANT CONNECT ON DATABASE surfsense TO electric;
GRANT USAGE ON SCHEMA public TO electric;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO electric;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO electric;

-- Grant permissions on future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO electric;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON SEQUENCES TO electric;

-- Note: Electric SQL will create its own publications automatically
-- We don't need to create publications here
