import argparse
import logging
import os
import sys

from .adapters import ADAPTERS
from . import store

log = logging.getLogger("discovery")


def crawl_once(conn, sources, max_requests=None):
    exit_code = 0
    for name in sources:
        kwargs = {}
        if name == "google_places":
            if not os.environ.get("GOOGLE_PLACES_API_KEY"):
                log.warning("GOOGLE_PLACES_API_KEY not set; skipping google_places")
                continue
            kwargs["max_requests"] = max_requests
        adapter = ADAPTERS[name](**kwargs)
        try:
            ins, upd = store.upsert_candidates(conn, adapter.fetch())
            log.info("%s: %d new, %d updated", name, ins, upd)
        except Exception:
            conn.rollback()
            log.exception("%s crawl failed", name)
            exit_code = 1
    log.info("dedupe: %d rows marked duplicate", store.run_dedupe(conn))
    return exit_code


def main(argv=None):
    p = argparse.ArgumentParser(prog="discovery")
    sub = p.add_subparsers(dest="cmd", required=True)
    sp_crawl = sub.add_parser("crawl", help="one-shot crawl")
    sp_crawl.add_argument("--source", action="append", choices=sorted(ADAPTERS),
                          help="crawl source (default: mawaqit only)")
    sp_crawl.add_argument("--max-requests", type=int, default=None, help="cap Google API requests")
    sp_migrate = sub.add_parser("migrate", help="run pending migrations")
    sp_init_db = sub.add_parser("init-db", help="legacy; runs migrate")
    sp_enrich = sub.add_parser("enrich", help="enrich rows from mawaqit-api")
    sp_enrich.add_argument("--limit", type=int, default=None, help="max rows to enrich")
    sp_enrich.add_argument("--delay", type=float, default=2, help="seconds between API calls")
    sp_enrich.add_argument("--max-age-days", type=int, default=30, help="re-enrich rows older than this")
    sp_enrich.add_argument("--slug", help="enrich specific slug only")

    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    conn = store.connect()
    if args.cmd == "migrate":
        store.migrate(conn)
        return 0
    if args.cmd == "init-db":
        store.migrate(conn)
        return 0

    store.init_schema(conn)

    if args.cmd == "crawl":
        sources = args.source or ["mawaqit"]
        exit_code = crawl_once(conn, sources, args.max_requests)
        return exit_code

    if args.cmd == "enrich":
        from . import enrich as enrich_module
        exit_code = enrich_module.enrich(conn, limit=args.limit, delay=args.delay,
                                         max_age_days=args.max_age_days, slug=args.slug)
        return exit_code

    return 1


if __name__ == "__main__":
    sys.exit(main())
