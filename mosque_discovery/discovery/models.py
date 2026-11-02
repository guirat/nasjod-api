from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Candidate:
    """A mosque as reported by a source, before it is stored."""
    source: str
    source_id: str
    name: str
    lat: float
    lon: float
    name_ar: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    country: Optional[str] = "Tunisia"
    phone: Optional[str] = None
    raw: dict = field(default_factory=dict)


def has_arabic(text):
    return bool(text) and any("؀" <= c <= "ۿ" for c in text)
