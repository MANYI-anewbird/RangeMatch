"""Ephemeral investigation storage.

Prototype default is in-memory and thread-safe. Process restart clears all
records. Swap InMemoryInvestigationStore for a durable backend later without
changing API handlers.
"""

from __future__ import annotations

import threading
from copy import deepcopy
from typing import Any, Protocol


INVESTIGATION_TERMINAL_STATUSES = frozenset(
    {
        "COMPLETED",
        "PARTIAL",
        "FAILED",
        "BLOCKED_EXTERNAL",
        "BLOCKED_INPUT",
    }
)
INVESTIGATION_ACTIVE_STATUSES = frozenset({"QUEUED", "RUNNING"})


class InvestigationStore(Protocol):
    def put(self, record: dict[str, Any]) -> None: ...

    def get(self, investigation_id: str) -> dict[str, Any] | None: ...

    def update(self, investigation_id: str, patch: dict[str, Any]) -> dict[str, Any] | None: ...

    def try_claim(self, investigation_id: str) -> bool: ...

    def clear(self) -> None: ...


class InMemoryInvestigationStore:
    """Process-local dict store with claim lock for single-flight execution."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._records: dict[str, dict[str, Any]] = {}

    def put(self, record: dict[str, Any]) -> None:
        iid = record.get("investigation_id")
        if not iid:
            raise ValueError("investigation_id_required")
        with self._lock:
            self._records[str(iid)] = deepcopy(record)

    def get(self, investigation_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._records.get(investigation_id)
            return deepcopy(record) if record is not None else None

    def update(self, investigation_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        with self._lock:
            record = self._records.get(investigation_id)
            if record is None:
                return None
            record.update(deepcopy(patch))
            return deepcopy(record)

    def try_claim(self, investigation_id: str) -> bool:
        """Atomically claim QUEUED → RUNNING. Returns False if already claimed/terminal."""
        with self._lock:
            record = self._records.get(investigation_id)
            if record is None:
                return False
            if record.get("status") != "QUEUED":
                return False
            if record.get("execution_claimed"):
                return False
            record["status"] = "RUNNING"
            record["execution_claimed"] = True
            return True

    def clear(self) -> None:
        with self._lock:
            self._records.clear()


INVESTIGATION_STORE: InvestigationStore = InMemoryInvestigationStore()


def get_investigation_store() -> InvestigationStore:
    return INVESTIGATION_STORE


def reset_investigation_store_for_tests() -> None:
    INVESTIGATION_STORE.clear()


def public_investigation_view(record: dict[str, Any]) -> dict[str, Any]:
    """API projection: omit internal job payload and optionally strip trace."""
    return {
        k: v
        for k, v in record.items()
        if k not in {"trace", "_job", "execution_claimed"}
    }
