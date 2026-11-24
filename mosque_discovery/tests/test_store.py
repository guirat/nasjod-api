"""DB tests; run only when STAGING_TEST_DATABASE_URL points at a PostGIS database."""
import os

import pytest

from discovery import store
from discovery.models import Candidate

url = os.environ.get("STAGING_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not url, reason="STAGING_TEST_DATABASE_URL not set")


@pytest.fixture
def conn():
    c = store.connect(url)
    store.init_schema(c)
    with c.cursor() as cur:
        cur.execute("TRUNCATE staged_mosque RESTART IDENTITY CASCADE")
    c.commit()
    yield c
    c.close()


def test_upsert_keeps_status_and_dedupes(conn):
    c1 = Candidate("mawaqit", "m1", "جامع النور", 34.7, 10.7)
    assert store.upsert_candidates(conn, [c1]) == (1, 0)
    with conn.cursor() as cur:
        cur.execute("UPDATE staged_mosque SET status='approved'")
    conn.commit()
    c1.name = "changed"
    assert store.upsert_candidates(conn, [c1]) == (0, 1)
    store.upsert_candidates(conn, [Candidate("google_places", "g1", "جامع النور", 34.7001, 10.7)])
    assert store.run_dedupe(conn) == 1
    with conn.cursor() as cur:
        cur.execute("SELECT source, status, name FROM staged_mosque ORDER BY id")
        assert cur.fetchall() == [("mawaqit", "approved", "changed"), ("google_places", "duplicate", "جامع النور")]
