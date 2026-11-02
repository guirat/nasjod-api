"""Google Places (New) adapter.

Uses Text Search (New): POST https://places.googleapis.com/v1/places:searchText
with includedType=mosque and a rectangular locationRestriction. Each query returns
at most 20 results/page and 60 total, so the search is a quadtree: start with
coarse cells over Tunisia's bounding box and split any cell that hits the 60-result
cap until it is smaller than MIN_CELL_DEG. Results are filtered to country code TN.

The API key is read from env GOOGLE_PLACES_API_KEY (never committed). Cost: each
page is a billable Text Search request (Pro SKU because of the phone field);
use `crawl --max-requests N` to cap a run.
"""
import logging
import os
import time
from typing import Iterator

import requests

from .base import SourceAdapter, USER_AGENT
from ..models import Candidate, has_arabic

log = logging.getLogger(__name__)
URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = ",".join([
    "nextPageToken", "places.id", "places.displayName", "places.formattedAddress",
    "places.location", "places.addressComponents", "places.nationalPhoneNumber",
    "places.internationalPhoneNumber", "places.types", "places.businessStatus",
])
# south, west, north, east
TUNISIA_BBOX = (30.2, 7.5, 37.6, 11.7)
PAGE_CAP = 60


class RequestBudgetExceeded(Exception):
    pass


class GooglePlacesAdapter(SourceAdapter):
    name = "google_places"

    def __init__(self, api_key=None, session=None, bbox=TUNISIA_BBOX, initial_cell=1.0,
                 min_cell=0.02, max_requests=None, sleep=time.sleep, queries=("mosque",)):
        self.api_key = api_key or os.environ.get("GOOGLE_PLACES_API_KEY")
        self.session = session or requests.Session()
        self.bbox, self.initial_cell, self.min_cell = bbox, initial_cell, min_cell
        self.max_requests = max_requests
        self.requests_made = 0
        self.sleep = sleep
        self.queries = queries

    def _post(self, body):
        if self.max_requests is not None and self.requests_made >= self.max_requests:
            raise RequestBudgetExceeded(f"max_requests={self.max_requests} reached")
        self.requests_made += 1
        headers = {"X-Goog-Api-Key": self.api_key, "X-Goog-FieldMask": FIELD_MASK,
                   "Content-Type": "application/json", "User-Agent": USER_AGENT}
        for attempt in range(1, 4):
            resp = self.session.post(URL, json=body, headers=headers, timeout=30)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (429, 500, 503) and attempt < 3:
                self.sleep(2 * attempt)
                continue
            resp.raise_for_status()

    def _search_cell(self, cell, query):
        """Return (places, capped) for one rectangle, following page tokens."""
        s, w, n, e = cell
        body = {
            "textQuery": query, "includedType": "mosque", "pageSize": 20,
            "locationRestriction": {"rectangle": {
                "low": {"latitude": s, "longitude": w},
                "high": {"latitude": n, "longitude": e}}},
        }
        places = []
        while True:
            data = self._post(body)
            places.extend(data.get("places", []))
            token = data.get("nextPageToken")
            if not token or len(places) >= PAGE_CAP:
                break
            body["pageToken"] = token
        return places, len(places) >= PAGE_CAP

    def _initial_cells(self):
        s, w, n, e = self.bbox
        step = self.initial_cell
        lat = s
        while lat < n:
            lon = w
            while lon < e:
                yield (lat, lon, min(lat + step, n), min(lon + step, e))
                lon += step
            lat += step

    def fetch(self) -> Iterator[Candidate]:
        seen = set()
        stack = list(self._initial_cells())
        while stack:
            cell = stack.pop()
            for query in self.queries:
                places, capped = self._search_cell(cell, query)
                for p in places:
                    c = self.parse(p)
                    if c and c.source_id not in seen:
                        seen.add(c.source_id)
                        yield c
                if capped:
                    s, w, n, e = cell
                    if (n - s) / 2 >= self.min_cell:
                        ms, mw = (s + n) / 2, (w + e) / 2
                        stack += [(s, w, ms, mw), (s, mw, ms, e), (ms, w, n, mw), (ms, mw, n, e)]
                        break  # sub-cells will re-run all queries
                    log.warning("cell %s still capped at min size; results may be incomplete", cell)

    @staticmethod
    def parse(p):
        loc = p.get("location") or {}
        try:
            lat, lon, pid = float(loc["latitude"]), float(loc["longitude"]), p["id"]
        except (KeyError, TypeError, ValueError):
            return None
        comps = p.get("addressComponents") or []

        def comp(kind, field="longText"):
            for c in comps:
                if kind in c.get("types", []):
                    return c.get(field)
        if comp("country", "shortText") not in (None, "TN"):
            return None
        if p.get("businessStatus") in ("CLOSED_PERMANENTLY",):
            return None
        name = ((p.get("displayName") or {}).get("text") or "").strip()
        return Candidate(
            source="google_places", source_id=pid, name=name,
            name_ar=name if has_arabic(name) else None, lat=lat, lon=lon,
            address=p.get("formattedAddress"),
            city=comp("locality") or comp("administrative_area_level_2"),
            state=comp("administrative_area_level_1"),
            zip_code=comp("postal_code"), country="Tunisia",
            phone=p.get("internationalPhoneNumber") or p.get("nationalPhoneNumber"),
            raw=p,
        )
