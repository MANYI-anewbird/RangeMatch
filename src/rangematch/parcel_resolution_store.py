"""Ephemeral parcel-resolution storage.

Prototype default is in-memory. Process restart clears all records.
Replace InMemoryParcelResolutionStore with a durable backend later without
changing API handlers.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Protocol


class ParcelResolutionStore(Protocol):
    def put(self, record: dict[str, Any]) -> None: ...

    def get(self, resolution_id: str) -> dict[str, Any] | None: ...

    def clear(self) -> None: ...


class InMemoryParcelResolutionStore:
    """Process-local dict store. Restart clears state."""

    def __init__(self) -> None:
        self._records: dict[str, dict[str, Any]] = {}

    def put(self, record: dict[str, Any]) -> None:
        rid = record.get("resolution_id")
        if not rid:
            raise ValueError("resolution_id_required")
        self._records[str(rid)] = deepcopy(record)

    def get(self, resolution_id: str) -> dict[str, Any] | None:
        record = self._records.get(resolution_id)
        return deepcopy(record) if record is not None else None

    def clear(self) -> None:
        self._records.clear()


# Module-level prototype store (swap for persistence later).
PARCEL_RESOLUTION_STORE: ParcelResolutionStore = InMemoryParcelResolutionStore()


def get_parcel_resolution_store() -> ParcelResolutionStore:
    return PARCEL_RESOLUTION_STORE


def reset_parcel_resolution_store_for_tests() -> None:
    PARCEL_RESOLUTION_STORE.clear()
