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

-- Create the publication that Electric SQL expects
-- Electric will add tables to this publication when shapes are subscribed
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_publication WHERE pubname = 'electric_publication_default') THEN
        CREATE PUBLICATION electric_publication_default;
    END IF;
END
$$;
