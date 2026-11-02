"""Distance and name-similarity helpers shared by dedupe and tests."""
import math
import re
import unicodedata
from difflib import SequenceMatcher

# Generic words that say "mosque" in the languages seen in Tunisian data.
GENERIC = {
    "mosque", "mosquee", "masjid", "mesjid", "jamaa", "jema", "jemaa", "jamea", "jami", "djamaa",
    "el", "al", "de", "la", "le", "du", "cite", "rue",
    "مسجد", "جامع", "الجامع", "المسجد", "جامعة",
}
_AR_DIACRITICS = re.compile("[ؐ-ًؚ-ٰٟـ]")


def haversine_m(lat1, lon1, lat2, lon2):
    r = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def normalize_name(name):
    if not name:
        return ""
    s = unicodedata.normalize("NFKD", name.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = _AR_DIACRITICS.sub("", s)
    s = s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه").replace("ى", "ي")
    s = re.sub(r"[^\w\s]", " ", s)
    tokens = [t for t in s.split() if t not in GENERIC]
    return " ".join(tokens)


def name_similarity(a, b):
    """0..1 similarity ignoring generic 'mosque' words. 0 if either side is empty."""
    na, nb = normalize_name(a), normalize_name(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()
