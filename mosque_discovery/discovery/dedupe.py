"""Cross-source dedupe: Mawaqit vs Google rows describing the same mosque."""
from collections import defaultdict

from .geo import haversine_m, name_similarity

# Same mosque if: very close, or close with a similar name.
HARD_DISTANCE_M = 40
NEAR_DISTANCE_M = 150
NAME_THRESHOLD = 0.6
PREFERRED_SOURCE = "mawaqit"  # canonical row: it carries the prayer-time data


def is_same_mosque(a, b):
    d = haversine_m(a["lat"], a["lon"], b["lat"], b["lon"])
    if d <= HARD_DISTANCE_M:
        return True, d, name_similarity(a["name"], b["name"])
    if d <= NEAR_DISTANCE_M:
        sim = max(name_similarity(a["name"], b["name"]), name_similarity(a.get("name_ar"), b["name"]),
                  name_similarity(a["name"], b.get("name_ar")))
        return sim >= NAME_THRESHOLD, d, sim
    return False, d, 0.0


def find_duplicates(rows):
    """rows: dicts with id, source, name, name_ar, lat, lon.
    Returns {duplicate_id: canonical_id} for rows of a non-preferred source that
    match a row of the preferred source."""
    cell = 0.003  # ~330 m buckets
    buckets = defaultdict(list)
    for r in rows:
        if r["source"] == PREFERRED_SOURCE:
            buckets[(int(r["lat"] / cell), int(r["lon"] / cell))].append(r)
    out = {}
    for r in rows:
        if r["source"] == PREFERRED_SOURCE:
            continue
        ci, cj = int(r["lat"] / cell), int(r["lon"] / cell)
        best = None
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for cand in buckets.get((ci + di, cj + dj), ()):
                    same, dist, _ = is_same_mosque(r, cand)
                    if same and (best is None or dist < best[0]):
                        best = (dist, cand["id"])
        if best:
            out[r["id"]] = best[1]
    return out
