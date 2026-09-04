from __future__ import annotations
from abc import ABC, abstractmethod
from backend.api.schemas import NormalizedTransaction


class BaseChainAdapter(ABC):
    """Every chain adapter (live or stub) must implement this."""

    @abstractmethod
    def fetch_transactions(self, address: str) -> list[NormalizedTransaction]:
        ...