-- Electrify tables for Electric SQL sync
-- This tells Electric SQL which tables to sync
-- Run this after running migrations

-- Electrify notifications table
ALTER TABLE notifications ENABLE ELECTRIC;

-- You can electrify other tables as needed:
-- ALTER TABLE documents ENABLE ELECTRIC;
-- ALTER TABLE logs ENABLE ELECTRIC;

