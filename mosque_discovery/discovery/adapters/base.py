from abc import ABC, abstractmethod
from typing import Iterator

from ..models import Candidate

USER_AGENT = "nasjod-mosque-discovery/1.0 (+https://nasjod.com; contact: tech@nasjod.com)"


class SourceAdapter(ABC):
    """Common interface: yield every Tunisian mosque the source knows about."""
    name: str

    @abstractmethod
    def fetch(self) -> Iterator[Candidate]:
        ...
