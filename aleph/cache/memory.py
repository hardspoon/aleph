"""In-memory cache."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(slots=True)
class MemoryCache(Generic[T]):
    """Very small, process-local cache.

    This is primarily used to memoize repeated sub_query calls.
    """

    _store: dict[str, T] = field(default_factory=dict)

    def get(self, key: str) -> T | None:
        return self._store.get(key)

    def set(self, key: str, value: T) -> None:
        self._store[key] = value

    def clear(self) -> None:
        self._store.clear()
