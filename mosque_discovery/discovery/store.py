import glob
import json
import logging
import os

import psycopg2
import psycopg2.extras

from .dedupe import find_duplicates

log = logging.getLogger("discovery")
MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "migrations")

UPSERT = """
INSERT INTO staged_mosque (source, source_id, name, name_ar, lat, lon, geom, address, city, state,
                           zip_code, country, phone, raw)
VALUES (%(source)s, %(source_id)s, %(name)s, %(name_ar)s, %(lat)s, %(lon)s,
        ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography, %(address)s, %(city)s,
        %(state)s, %(zip_code)s, %(country)s, %(phone)s, %(raw)s)
ON CONFLICT (source, source_id) DO UPDATE SET
    name = EXCLUDED.name, name_ar = EXCLUDED.name_ar, lat = EXCLUDED.lat, lon = EXCLUDED.lon,
    geom = EXCLUDED.geom, address = EXCLUDED.address, city = EXCLUDED.city, state = EXCLUDED.state,
    zip_code = EXCLUDED.zip_code, country = EXCLUDED.country, phone = EXCLUDED.phone,
    raw = EXCLUDED.raw, last_seen = now()
RETURNING (xmax = 0) AS inserted
"""  # status / matched_* are intentionally never touched on update


def connect(url=None):
    return psycopg2.connect(url or os.environ["STAGING_DATABASE_URL"])


def _ensure_migrations_table(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
    conn.commit()


def _get_applied_migrations(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT version FROM schema_migrations ORDER BY version")
        return {row[0] for row in cur.fetchall()}


def _get_migration_files():
    """Return list of migration files in order: (version, up_path, down_path or None)."""
    migrations = []
    for up_path in sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql"))):
        filename = os.path.basename(up_path)
        if filename.endswith(".down.sql"):
            continue
        version = filename[:-4]  # remove .sql
        down_path = up_path[:-4] + ".down.sql"
        down_path = down_path if os.path.exists(down_path) else None
        migrations.append((version, up_path, down_path))
    return migrations


def _adopt_existing_db(conn):
    """Record 0001 as applied if staged_mosque exists but schema_migrations doesn't."""
    _ensure_migrations_table(conn)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name='staged_mosque'
            )
        """)
        staged_exists = cur.fetchone()[0]

    if staged_exists:
        applied = _get_applied_migrations(conn)
        if "0001_initial" not in applied:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s)",
                    ("0001_initial",)
                )
            conn.commit()
            log.info("Recorded 0001_initial as applied (adopted existing DB)")


def migrate(conn):
    """Apply all pending migrations in order."""
    _ensure_migrations_table(conn)
    _adopt_existing_db(conn)

    applied = _get_applied_migrations(conn)
    migrations = _get_migration_files()

    for version, up_path, down_path in migrations:
        if version in applied:
            log.debug("Skipping already-applied migration %s", version)
            continue

        log.info("Applying migration %s", version)
        with open(up_path) as f:
            sql = f.read()

        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s)",
                (version,)
            )
        conn.commit()
        log.info("Migration %s applied", version)


def init_schema(conn):
    """Legacy function; calls migrate."""
    migrate(conn)


def upsert_candidates(conn, candidates):
    """Upsert on (source, source_id). Returns (inserted, updated)."""
    ins = upd = 0
    with conn.cursor() as cur:
        for c in candidates:
            params = dict(c.__dict__, raw=json.dumps(c.raw))
            cur.execute(UPSERT, params)
            if cur.fetchone()[0]:
                ins += 1
            else:
                upd += 1
    conn.commit()
    return ins, upd


def run_dedupe(conn):
    """Mark non-canonical cross-source rows (status 'new' only) as duplicate. Returns count."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT id, source, name, name_ar, lat, lon, status FROM staged_mosque")
        rows = cur.fetchall()
    dups = find_duplicates(rows)
    status = {r["id"]: r["status"] for r in rows}
    n = 0
    with conn.cursor() as cur:
        for dup_id, canon_id in dups.items():
            if status[dup_id] == "new":
                cur.execute("UPDATE staged_mosque SET status='duplicate', duplicate_of_id=%s WHERE id=%s",
                            (canon_id, dup_id))
                n += 1
    conn.commit()
    return n
