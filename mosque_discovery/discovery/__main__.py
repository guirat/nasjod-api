import argparse
import logging
import os
import sys
import time

from .adapters import ADAPTERS
from . import store

log = logging.getLogger("discovery")


def crawl_once(conn, sources, max_requests=None):
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
    log.info("dedupe: %d rows marked duplicate", store.run_dedupe(conn))


def main(argv=None):
    p = argparse.ArgumentParser(prog="discovery")
    sub = p.add_subparsers(dest="cmd", required=True)
    for cmd in ("crawl", "loop"):
        sp = sub.add_parser(cmd)
        sp.add_argument("--source", action="append", choices=sorted(ADAPTERS))
        sp.add_argument("--max-requests", type=int, default=None, help="cap Google API requests per run")
    sub.choices["crawl"].add_argument("--once", action="store_true", help="(default) single run")
    sub.choices["loop"].add_argument("--interval-hours", type=float,
                                     default=float(os.environ.get("CRAWL_INTERVAL_HOURS", 168)))
    sub.add_parser("migrate")
    sub.add_parser("init-db")
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
    sources = args.source or list(ADAPTERS)
    if args.cmd == "crawl":
        crawl_once(conn, sources, args.max_requests)
        return 0
    while True:
        crawl_once(conn, sources, args.max_requests)
        conn.close()  # don't hold a connection open for days
        time.sleep(args.interval_hours * 3600)
        conn = store.connect()


if __name__ == "__main__":
    sys.exit(main())
