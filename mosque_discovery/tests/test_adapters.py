import pytest

from discovery.adapters.google_places import GooglePlacesAdapter, PAGE_CAP
from discovery.adapters.mawaqit import MawaqitAdapter


class Resp:
    def __init__(self, status=200, data=None):
        self.status_code, self._data = status, data

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class FakeSession:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    def _next(self, *a, **kw):
        self.calls.append((a, kw))
        r = self.responses.pop(0)
        return r(a, kw) if callable(r) else r

    get = post = _next


MW_ITEM = {"slug": "m-x", "name": "جامع النور", "address": "Rue 1", "city": "Sfax",
           "zipcode": "3000", "countryFullName": "Tunisia", "lat": 34.7, "lng": 10.7, "image1": "u"}


def test_mawaqit_parse_and_retry():
    s = FakeSession([Resp(503), Resp(200, [MW_ITEM, {"slug": "bad", "lat": "x", "lng": 1}])])
    out = list(MawaqitAdapter(session=s, sleep=lambda _: None).fetch())
    assert len(out) == 1 and len(s.calls) == 2
    c = out[0]
    assert (c.source, c.source_id, c.lat, c.lon, c.zip_code) == ("mawaqit", "m-x", 34.7, 10.7, "3000")
    assert c.name_ar == "جامع النور" and c.raw["slug"] == "m-x"
    assert "mosque/map/TN" in s.calls[0][0][0]


def test_mawaqit_gives_up():
    s = FakeSession([Resp(500)] * 3)
    with pytest.raises(RuntimeError):
        list(MawaqitAdapter(session=s, sleep=lambda _: None).fetch())


def place(pid, country="TN", lat=36.8, lon=10.1, name="Mosquée X", status=None):
    return {"id": pid, "displayName": {"text": name}, "formattedAddress": "addr",
            "location": {"latitude": lat, "longitude": lon}, "internationalPhoneNumber": "+216 1",
            "addressComponents": [{"types": ["country"], "shortText": country, "longText": "x"},
                                  {"types": ["locality"], "longText": "Tunis"}],
            **({"businessStatus": status} if status else {})}


def test_google_parse_filters():
    g = GooglePlacesAdapter.parse
    c = g(place("a"))
    assert c.city == "Tunis" and c.phone == "+216 1" and c.source_id == "a"
    assert g(place("b", country="DZ")) is None
    assert g(place("c", status="CLOSED_PERMANENTLY")) is None


def test_google_paginates_and_dedupes_across_cells():
    s = FakeSession([
        Resp(200, {"places": [place("a"), place("b")], "nextPageToken": "t"}),
        Resp(200, {"places": [place("b"), place("c")]}),
    ])
    ad = GooglePlacesAdapter(api_key="k", session=s, bbox=(36, 10, 37, 11), initial_cell=1.0)
    out = list(ad.fetch())
    assert [c.source_id for c in out] == ["a", "b", "c"]
    assert s.calls[1][1]["json"]["pageToken"] == "t"
    assert s.calls[0][1]["headers"]["X-Goog-Api-Key"] == "k"


def test_google_subdivides_capped_cell():
    full = [Resp(200, {"places": [place(f"p{i}-{j}") for i in range(20)], "nextPageToken": "t"})
            for j in range(2)]
    last = Resp(200, {"places": [place(f"z{i}") for i in range(20)]})
    sub = [Resp(200, {"places": [place("s")]}) for _ in range(4)]
    s = FakeSession(full + [last] + sub)
    ad = GooglePlacesAdapter(api_key="k", session=s, bbox=(36, 10, 37, 11), initial_cell=1.0)
    out = list(ad.fetch())
    assert len(s.calls) == 3 + 4  # capped cell (60 results) -> 4 sub-cells
    assert len(out) == PAGE_CAP + 1  # 's' is deduped across the 4 sub-cells


def test_google_request_budget():
    from discovery.adapters.google_places import RequestBudgetExceeded
    s = FakeSession([Resp(200, {"places": [place("a")]})] * 5)
    ad = GooglePlacesAdapter(api_key="k", session=s, bbox=(36, 10, 38, 12), initial_cell=1.0, max_requests=2)
    with pytest.raises(RequestBudgetExceeded):
        list(ad.fetch())
    assert len(s.calls) == 2
