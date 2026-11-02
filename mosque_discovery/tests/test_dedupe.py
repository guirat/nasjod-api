from discovery.dedupe import find_duplicates
from discovery.geo import haversine_m, name_similarity, normalize_name


def row(i, source, name, lat, lon, name_ar=None):
    return dict(id=i, source=source, name=name, name_ar=name_ar, lat=lat, lon=lon)


def test_haversine():
    assert 105_000 < haversine_m(36.0, 10.0, 37.0, 10.0) < 117_000
    assert haversine_m(36, 10, 36, 10) == 0


def test_name_similarity_ignores_generic_words():
    assert normalize_name("Mosquée El Nour") == normalize_name("Masjid Nour")
    assert name_similarity("جامع النور", "مسجد النور") > 0.9
    assert name_similarity("Mosquée Ennour", "Mosquée Zitouna") < 0.6
    assert name_similarity("", "x") == 0


def test_same_place_flagged_google_is_duplicate():
    rows = [row(1, "mawaqit", "جامع النور", 34.7000, 10.7000),
            row(2, "google_places", "جامع النور", 34.7003, 10.7002)]  # ~40 m
    assert find_duplicates(rows) == {2: 1}


def test_near_requires_similar_name():
    rows = [row(1, "mawaqit", "Mosquée Ennour", 34.7000, 10.7000),
            row(2, "google_places", "Mosquée Zitouna", 34.7008, 10.7000),    # ~90 m, other name
            row(3, "google_places", "Masjid Ennour", 34.7008, 10.7000)]      # ~90 m, same name
    assert find_duplicates(rows) == {3: 1}


def test_far_apart_not_duplicate_and_picks_closest():
    rows = [row(1, "mawaqit", "A", 34.7, 10.7), row(2, "mawaqit", "A", 34.7002, 10.7),
            row(3, "google_places", "A", 34.7001, 10.7), row(4, "google_places", "A", 34.8, 10.7)]
    d = find_duplicates(rows)
    assert 4 not in d and d[3] in (1, 2)


def test_same_source_never_deduped():
    rows = [row(1, "google_places", "A", 34.7, 10.7), row(2, "google_places", "A", 34.7, 10.7)]
    assert find_duplicates(rows) == {}
