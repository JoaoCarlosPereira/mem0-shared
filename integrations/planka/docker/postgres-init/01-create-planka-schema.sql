-- Mem0 Shared: PLANKA sidecar schema on the shared OpenMemory database.
-- Mounted into Postgres docker-entrypoint-initdb.d (runs only on empty data volume).
-- For existing volumes, start-mem0.sh / ensure-schema.js creates the schema at boot.

CREATE SCHEMA IF NOT EXISTS planka;
GRANT ALL ON SCHEMA planka TO CURRENT_USER;
GRANT ALL ON SCHEMA planka TO PUBLIC;
