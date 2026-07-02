-- Run once on first boot by the PostGIS docker image.
-- Extensions are also created by Alembic migration 0001,
-- but we ensure they exist here so the migration can run.
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pgcrypto;
