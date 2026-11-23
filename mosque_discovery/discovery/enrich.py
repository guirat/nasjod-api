"""Enrichment via self-hosted mawaqit-api."""
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone

import psycopg2.extras
import requests

from .adapters.base import USER_AGENT

log = logging.getLogger(__name__)


def enrich(conn, limit=None, delay=2, max_age_days=30, slug=None):
    """Enrich staging rows with details from mawaqit-api.

    For each selected row (source=mawaqit, status in new/approved, enriched_at null or older),
    fetch details from mawaqit-api and store in details JSONB column.

    Args:
        conn: database connection
        limit: max rows to enrich in this run
        delay: seconds between API calls
        max_age_days: re-enrich rows older than this many days
        slug: if set, enrich only this specific slug

    Returns:
        0 if mawaqit-api was reachable or skipped, 1 if unreachable
    """
    api_url = os.environ.get("MAWAQIT_API_URL")
    api_token = os.environ.get("MAWAQIT_API_TOKEN")

    if not api_url:
        log.warning("MAWAQIT_API_URL not set; skipping enrich")
        return 0

    if not api_token:
        log.error("MAWAQIT_API_TOKEN required for enrich")
        return 1

    api_url = api_url.rstrip('/')
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=max_age_days)

    # Select rows to enrich
    query = """
        SELECT id, source_id FROM staged_mosque
        WHERE source = 'mawaqit'
          AND status IN ('new', 'approved')
          AND (enriched_at IS NULL OR enriched_at < %s)
    """
    params = [cutoff_time]

    if slug:
        query += " AND source_id = %s"
        params.append(slug)

    query += " ORDER BY enriched_at ASC NULLS FIRST"

    if limit:
        query += " LIMIT %s"
        params.append(limit)

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query, params)
        rows = cur.fetchall()

    if not rows:
        log.info("No rows to enrich")
        return 0

    log.info("Enriching %d rows", len(rows))
    session = requests.Session()
    headers = {"User-Agent": USER_AGENT, "Authorization": f"Bearer {api_token}"}
    exit_code = 0

    for row in rows:
        row_id = row["id"]
        row_slug = row["source_id"]
        endpoint = f"{api_url}/api/v1/{row_slug}/"

        try:
            resp = session.get(endpoint, headers=headers, timeout=30)

            if resp.status_code == 200:
                details = resp.json()
                with conn.cursor() as cur:
                    cur.execute(
                        """UPDATE staged_mosque SET details=%s, enriched_at=now(), enrich_error=NULL
                           WHERE id=%s""",
                        (json.dumps(details), row_id)
                    )
                conn.commit()
                log.debug("Enriched %s", row_slug)

            elif resp.status_code == 404:
                with conn.cursor() as cur:
                    cur.execute(
                        """UPDATE staged_mosque SET enrich_error='not_found', enriched_at=now()
                           WHERE id=%s""",
                        (row_id,)
                    )
                conn.commit()
                log.debug("Not found: %s", row_slug)

            elif resp.status_code in (429, 500, 502, 503, 504):
                log.warning("API error %d for %s; will retry later", resp.status_code, row_slug)
                # Don't update enriched_at; retry on next run

            else:
                msg = f"HTTP {resp.status_code}"
                with conn.cursor() as cur:
                    cur.execute(
                        """UPDATE staged_mosque SET enrich_error=%s, enriched_at=now()
                           WHERE id=%s""",
                        (msg, row_id)
                    )
                conn.commit()
                log.warning("API error %s for %s", msg, row_slug)

        except requests.Timeout:
            log.warning("Timeout enriching %s; will retry later", row_slug)

        except Exception as e:
            msg = str(e)[:100]
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE staged_mosque SET enrich_error=%s, enriched_at=now()
                       WHERE id=%s""",
                    (msg, row_id)
                )
            conn.commit()
            log.warning("Error enriching %s: %s", row_slug, e)

        time.sleep(delay)

    log.info("Enrichment complete")
    return exit_code
