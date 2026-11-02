import json
import os

import psycopg2
import psycopg2.extras

from .dedupe import find_duplicates

SCHEMA = os.path.join(os.path.dirname(__file__), "..", "schema.sql")

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


def init_schema(conn):
    with open(SCHEMA) as f, conn.cursor() as cur:
        cur.execute(f.read())
    conn.commit()


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
