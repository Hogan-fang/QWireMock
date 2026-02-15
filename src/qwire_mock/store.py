"""In-memory store keyed by order reference (UUID)."""

from threading import Lock
from uuid import UUID

from qwire_mock.schemas import OrderResponse


class OrderStore:
    """Thread-safe in-memory cache of OrderResponse by reference."""

    def __init__(self) -> None:
        self._data: dict[UUID, OrderResponse] = {}
        self._lock = Lock()

    def put(self, reference: UUID, order: OrderResponse) -> None:
        with self._lock:
            self._data[reference] = order

    def get(self, reference: UUID) -> OrderResponse | None:
        with self._lock:
            return self._data.get(reference)

    def delete(self, reference: UUID) -> bool:
        with self._lock:
            if reference in self._data:
                del self._data[reference]
                return True
            return False

    def list_all(self) -> list[OrderResponse]:
        """Return all cached orders (no ordering guarantee)."""
        with self._lock:
            return list(self._data.values())

    def clear(self) -> int:
        """Remove all entries; return count of cleared entries."""
        with self._lock:
            n = len(self._data)
            self._data.clear()
            return n


# Singleton used by API
order_store = OrderStore()
