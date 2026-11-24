from .base import SourceAdapter
from .mawaqit import MawaqitAdapter
from .google_places import GooglePlacesAdapter

ADAPTERS = {"mawaqit": MawaqitAdapter, "google_places": GooglePlacesAdapter}

__all__ = ["SourceAdapter", "MawaqitAdapter", "GooglePlacesAdapter", "ADAPTERS"]
