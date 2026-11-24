"""Pytest configuration for Django tests with staging database support."""
import os
import psycopg2
from pathlib import Path

import pytest


@pytest.fixture(scope="session", autouse=True)
def setup_staging_database():
    """Set up staging database schema for tests."""
    staging_url = os.environ.get("STAGING_DATABASE_URL")
    if not staging_url:
        return

    try:
        conn = psycopg2.connect(staging_url)

        # Apply migrations from mosque_discovery/migrations/*.sql
        migrations_dir = Path(__file__).parent.parent / "mosque_discovery" / "migrations"
        if migrations_dir.exists():
            for migration_file in sorted(migrations_dir.glob("*.sql")):
                # Skip .down.sql files
                if migration_file.suffix == ".sql" and ".down" not in migration_file.name:
                    with open(migration_file) as f:
                        sql = f.read()
                    with conn.cursor() as cur:
                        cur.execute(sql)
                    conn.commit()

        conn.close()
    except Exception as e:
        # Allow tests to continue even if setup fails
        # (they might skip tests that need the database)
        pass
