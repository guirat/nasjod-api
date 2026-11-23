# GUI-22: Mosque Discovery Staging Database Operations

## Setup (one-time, as postgres superuser)

Create a separate role and database for staging on the existing Postgres server:

```sql
-- Create staging role (not a superuser, only for staging DB access)
CREATE ROLE staging LOGIN PASSWORD 'password-here';

-- Create staging database owned by staging role
CREATE DATABASE staging OWNER staging;

-- Connect to staging database and enable PostGIS
\c staging
CREATE EXTENSION postgis;

-- Restrict staging role to only the staging database
-- (revoke connection to other databases, including main)
REVOKE CONNECT ON DATABASE postgres FROM staging;
REVOKE CONNECT ON DATABASE template0 FROM staging;
REVOKE CONNECT ON DATABASE template1 FROM staging;
-- If there is a main database, also revoke:
-- REVOKE CONNECT ON DATABASE <main_db_name> FROM staging;

-- Verify: staging role should only be able to connect to staging DB
```

## Connection string

Set `STAGING_DATABASE_URL` in environment for discovery and app containers:

```
postgresql://staging:password@db:5432/staging
```

Where `db` is the hostname of the main Postgres server (e.g., `db` in docker-compose, 
or IP/FQDN in production).

## Discovery service

The discovery container:
- Connects only via `STAGING_DATABASE_URL` (never to main DB)
- Runs migrations on startup (or when `python -m discovery migrate` is called)
- Crawls new data with `python -m discovery crawl`
- Enriches data with `python -m discovery enrich` (requires mawaqit-api running)
- Has `restart: "no"` policy (run via Coolify scheduled tasks or manual invocation)

## Coolify scheduled tasks

Schedule both crawl and enrich to run regularly:

1. **Crawl** (e.g., weekly):
   ```
   docker compose run --rm discovery python -m discovery crawl
   ```

2. **Enrich** (e.g., daily, after crawl):
   ```
   docker compose run --rm discovery python -m discovery enrich
   ```

## Backup

The staging database is a separate Postgres database on the same server as the main DB.

**Verify that your backup strategy covers the `staging` database** (e.g., `backup_db_to_r2`).

If your backup script dumps only the main DB by name, add the `staging` database to the backup:

```bash
# Example: add to backup script
pg_dump postgresql://staging:password@localhost/staging | gzip > backup_staging_$(date +%s).sql.gz
```

## Monitoring

Check staging DB size and row counts:

```sql
-- Size of staging DB
SELECT pg_size_pretty(pg_database_size('staging'));

-- Row counts
SELECT status, COUNT(*) FROM staged_mosque GROUP BY status;

-- Recently enriched rows
SELECT source_id, enriched_at, enrich_error FROM staged_mosque 
WHERE enriched_at > now() - interval '1 day' 
ORDER BY enriched_at DESC;

-- Failed enrichments
SELECT source_id, enrich_error, COUNT(*) FROM staged_mosque 
WHERE enrich_error IS NOT NULL 
GROUP BY source_id, enrich_error;
```

## Security notes

- The `staging` role cannot connect to the main DB (REVOKE applied)
- Main DB credentials are never sent to discovery container
- mawaqit-api token is not sent to discovery until `enrich` command runs
- Discovery container can be isolated on a different network if needed
