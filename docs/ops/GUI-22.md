# GUI-22: Mosque Discovery Service - Operations Guide

## Overview

The mosque discovery service (`nasjod-discovery` image) discovers and enriches mosque data from Mawaqit, staging it for human review in a separate PostgreSQL database before importing into the main Masjid table.

**Key principle:** All discovery data is temporary and read-only until a human approves it in the Django admin.

## One-Time Setup

### 1. Create the Staging Database and Role

Run these commands as a superuser on the main PostgreSQL server:

```sql
-- Create staging role (non-superuser, read-write only to staging DB)
CREATE ROLE staging LOGIN PASSWORD '<strong_password>';

-- Create staging database
CREATE DATABASE staging OWNER staging;

-- Connect to staging DB and add PostGIS
\c staging
CREATE EXTENSION postgis;

-- Restrict staging role to this DB only
REVOKE CONNECT ON DATABASE $DB_NAME FROM PUBLIC;
GRANT CONNECT ON DATABASE $DB_NAME TO $DB_USER;
```

Verification: As the `staging` user, verify you cannot connect to the main DB:
```bash
psql postgresql://staging:<password>@localhost/<main_db_name>
# Should fail: permission denied
```

### 2. Set Environment Variables

The app and discovery containers need:

```bash
# Required on discovery container
STAGING_DATABASE_URL=postgresql://staging:<password>@postgres:5432/staging
MAWAQIT_API_TOKEN=<token>
MAWAQIT_API_URL=http://mawaqit_api  # Port 80, no public port exposed

# Optional on discovery
GOOGLE_PLACES_API_KEY=<key>  # Only if using Google Places adapter

# App container can optionally connect to staging (for the admin review UI)
STAGING_DATABASE_URL=postgresql://staging:<password>@postgres:5432/staging
```

Where:
- `<password>` is the password for the `staging` PostgreSQL role
- `<token>` is the MAWAQIT_API_TOKEN from your internal mawaqit-api service
- `<key>` is the Google Places API key (if using the Google adapter)

### 3. Configure Coolify Scheduled Tasks

The discovery service runs on demand via Coolify scheduled tasks. Set up two tasks:

**Task 1: Crawl**
- Image: `nasjod-discovery:latest`
- Command: `python -m discovery crawl`
- Schedule: Daily at 2 AM UTC (or as needed)
- Environment: inherit from deployment

**Task 2: Enrich**
- Image: `nasjod-discovery:latest`
- Command: `python -m discovery enrich --limit 100`
- Schedule: Daily at 3 AM UTC (after crawl, with time to spare)
- Environment: inherit from deployment

The `--limit` flag prevents long runs; use `--limit 0` to enrich all pending rows.

## Database Backup

**Not covered.** The `backup_db_to_r2` script dumps only `$DB_NAME` and does not include the `staging` database. Backing up the `staging` database is a **required follow-up**, as review decisions cannot be re-crawled and must be preserved.

To back up the staging database manually:
```bash
pg_dump -U staging postgresql://staging:<password>@<host>/staging > staging_backup.sql
```

## Monitoring

### Check Staging DB Size
```bash
psql -U staging -h <host> -d staging -c "SELECT pg_size_pretty(pg_database_size('staging'))"
```

### View Pending Rows
```bash
psql -U staging -h <host> -d staging -c "
SELECT status, COUNT(*) as count FROM staged_mosque GROUP BY status
"
```

### View Recent Errors
```bash
psql -U staging -h <host> -d staging -c "
SELECT source_id, enrich_error, enriched_at FROM staged_mosque 
WHERE enrich_error IS NOT NULL 
ORDER BY enriched_at DESC LIMIT 20
"
```

## Troubleshooting

### Discovery container won't start: "STAGING_DATABASE_URL is required"
Ensure the environment variable is set and the database exists.

### Enrich exits with error: "Cannot reach mawaqit-api"
- Verify mawaqit-api service is running: `docker ps | grep mawaqit_api`
- Check logs: `docker logs <container_id>`
- Verify MAWAQIT_API_TOKEN is set and correct
- Enrich will retry on the next scheduled run; no manual intervention needed

### Admin shows no staged mosques
- Verify STAGING_DATABASE_URL is set on the app container
- Check Django logs for database routing errors
- Ensure the user has the `staging_review.review_stagedmosque` permission

### Staging data is too old
Run the crawl task manually:
```bash
docker run --rm --env-file envs/discovery.env nasjod-discovery:latest \
  python -m discovery crawl
```

## Kill Switch

If Mawaqit objects to the discovery service, stop the scheduled tasks in Coolify and the data collection stops. Reviewed rows already in staging are unaffected; nothing has been published to the main Masjid table without explicit human approval.

## SQL Commands

### Full reset (dangerous: deletes all staging data)
```bash
psql -U staging -h <host> -d staging -c "TRUNCATE staged_mosque RESTART IDENTITY"
```

### Mark all rows as imported (skip review)
```bash
psql -U staging -h <host> -d staging -c "
UPDATE staged_mosque SET status='imported' WHERE status='approved'
"
```

### Undo a bad import
```bash
psql -U staging -h <host> -d staging -c "
UPDATE staged_mosque SET status='approved', matched_masjid_id=NULL 
WHERE source_id='<slug>' AND status='imported'
"
# Then delete the Masjid row from the main DB
```
