-- Shopping Companion - PostgreSQL Initialization
-- Runs once on first container start

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Grant privileges (user already created by POSTGRES_USER env var)
GRANT ALL PRIVILEGES ON DATABASE shoppingcompanion TO shopping;
