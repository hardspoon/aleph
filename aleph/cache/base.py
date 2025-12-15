"""Cache protocol."""

from __future__ import annotations

from typing import Protocol, TypeVar

T = TypeVar("T")


class Cache(Protocol[T]):
    """Simple cache interface."""

    def get(self, key: str) -> T | None:
        ...

    def set(self, key: str, value: T) -> None:
        ...

    def clear(self) -> None:
        ...
