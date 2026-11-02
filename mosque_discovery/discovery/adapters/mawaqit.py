"""Mawaqit adapter.

Mawaqit has no official public API. `/api/2.0/mosque/search` requires an
`Api-Access-Token` (401 without it), but the site's own map endpoint
`GET https://mawaqit.net/api/2.0/mosque/map/{ISO country code}` is unauthenticated
and returns every mosque of a country in a single JSON array (~2.5k for TN,
~1.3 MB): slug, name, address, city, zipcode, lat, lng, image1.

ToS / politeness: this is an undocumented endpoint and may change or be blocked;
Mawaqit's terms are not an explicit licence to bulk-copy their data. We make ONE
request per crawl, identify ourselves in the User-Agent, back off on 429/5xx, and
default to a weekly crawl. Rows land in staging only and need human approval. Get
written permission from Mawaqit (contact@mawaqit.net) before relying on this in
production. If they issue an API token, set MAWAQIT_API_TOKEN and it is sent as
`Api-Access-Token`.
"""
import logging
import os
import time
from typing import Iterator

import requests

from .base import SourceAdapter, USER_AGENT
from ..models import Candidate, has_arabic

log = logging.getLogger(__name__)
MAP_URL = "https://mawaqit.net/api/2.0/mosque/map/{country}"


class MawaqitAdapter(SourceAdapter):
    name = "mawaqit"

    def __init__(self, country="TN", session=None, retries=3, backoff=5.0, sleep=time.sleep):
        self.country = country
        self.session = session or requests.Session()
        self.retries = retries
        self.backoff = backoff
        self.sleep = sleep

    def _get(self):
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        token = os.environ.get("MAWAQIT_API_TOKEN")
        if token:
            headers["Api-Access-Token"] = token
        url = MAP_URL.format(country=self.country)
        for attempt in range(1, self.retries + 1):
            resp = self.session.get(url, headers=headers, timeout=60)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < self.retries:
                self.sleep(self.backoff * attempt)
                continue
            resp.raise_for_status()
        raise RuntimeError("unreachable")

    def fetch(self) -> Iterator[Candidate]:
        for item in self._get():
            c = self.parse(item)
            if c:
                yield c

    @staticmethod
    def parse(item):
        try:
            lat, lon = float(item["lat"]), float(item["lng"])
            slug = item["slug"]
        except (KeyError, TypeError, ValueError):
            return None
        if not slug or (lat == 0 and lon == 0):
            return None
        name = (item.get("name") or "").strip()
        return Candidate(
            source="mawaqit", source_id=slug, name=name,
            name_ar=name if has_arabic(name) else None,
            lat=lat, lon=lon,
            address=(item.get("address") or "").strip() or None,
            city=(item.get("city") or "").strip() or None,
            zip_code=(item.get("zipcode") or "").strip() or None,
            country=item.get("countryFullName") or "Tunisia",
            raw=item,
        )
