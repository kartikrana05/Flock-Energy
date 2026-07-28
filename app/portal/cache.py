import threading
import time
from typing import Any, Callable


class PagedCache:
    def __init__(self, fetch_page: Callable[[int], dict], ttl_seconds: int, enabled: bool = True):
        self._fetch_page = fetch_page
        self._ttl_seconds = ttl_seconds
        self._enabled = enabled
        self._lock = threading.Lock()
        self._items: list[dict] = []
        self._last_refreshed: float = 0.0

    def get_all(self) -> list[dict]:
        if self._is_stale():
            self._refresh()
        return self._items

    def clear(self) -> None:
        with self._lock:
            self._items = []
            self._last_refreshed = 0.0

    def _is_stale(self) -> bool:
        if not self._enabled:
            return True
        return (time.monotonic() - self._last_refreshed) > self._ttl_seconds

    def _refresh(self) -> None:
        with self._lock:
            if not self._is_stale():
                return

            first = self._fetch_page(1)
            items = list(first["data"])
            page_size = first["pageSize"]
            total_pages = (first["total"] + page_size - 1) // page_size

            try:
                for page in range(2, total_pages + 1):
                    items.extend(self._fetch_page(page)["data"])
            except Exception:
                if self._items:
                    return
                raise

            self._items = items
            self._last_refreshed = time.monotonic()


class KeyedCache:
    def __init__(self, fetch: Callable[[str], Any], ttl_seconds: int, enabled: bool = True):
        self._fetch = fetch
        self._ttl_seconds = ttl_seconds
        self._enabled = enabled
        self._lock = threading.Lock()
        self._entries: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any:
        if not self._enabled:
            return self._fetch(key)

        entry = self._entries.get(key)
        if entry and (time.monotonic() - entry[0]) <= self._ttl_seconds:
            return entry[1]

        with self._lock:
            entry = self._entries.get(key)
            if entry and (time.monotonic() - entry[0]) <= self._ttl_seconds:
                return entry[1]

            try:
                data = self._fetch(key)
            except Exception:
                if entry:
                    return entry[1]
                raise

            self._entries[key] = (time.monotonic(), data)
            return data

    def clear(self) -> None:
        with self._lock:
            self._entries = {}
