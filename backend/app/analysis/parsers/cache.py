"""Bounded content-addressed cache for parsed modules.

Parsing is the most expensive per-file step in the static analysis pipeline.
This cache lets unchanged source files skip re-parsing when a project is
analyzed more than once, or when only one file changes between runs. It stays
deterministic because the key is derived only from the file path, language, and
source text, so an edit to one file invalidates exactly that file.

Cached modules are shared between runs, so callers must treat them as
read-only. Downstream builders (dependency, call graph, CFG, data flow) read
modules without mutating them, which makes sharing safe. The cache is bounded
with LRU eviction and guarded by a lock so it can be shared across requests.
"""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from threading import Lock

from app.analysis.model import ModuleAST
from app.projects.languages import Language

type _Key = tuple[Language, str, str]


class ParseCache:
    """Cache :class:`ModuleAST` values keyed by file content.

    ``capacity`` bounds the number of cached modules; when full, the
    least-recently-used entry is evicted. ``hit_count`` and ``miss_count`` are
    exposed for diagnostics, logging, and tests.
    """

    def __init__(self, capacity: int = 2048) -> None:
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        self._capacity = capacity
        self._entries: OrderedDict[_Key, ModuleAST] = OrderedDict()
        self._lock = Lock()
        self.hit_count = 0
        self.miss_count = 0

    @staticmethod
    def _key(language: Language, path: str, source: str) -> _Key:
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        return (language, path, digest)

    def get(self, language: Language, path: str, source: str) -> ModuleAST | None:
        """Return the cached module for ``source`` or ``None`` on a miss."""
        key = self._key(language, path, source)
        with self._lock:
            module = self._entries.get(key)
            if module is None:
                self.miss_count += 1
                return None
            self._entries.move_to_end(key)
            self.hit_count += 1
            return module

    def put(self, language: Language, path: str, source: str, module: ModuleAST) -> None:
        """Store ``module`` for ``source``, evicting least-recent entries past capacity."""
        key = self._key(language, path, source)
        with self._lock:
            if key in self._entries:
                self._entries.move_to_end(key)
            self._entries[key] = module
            while len(self._entries) > self._capacity:
                self._entries.popitem(last=False)

    def clear(self) -> None:
        """Drop every cached module and reset the hit/miss counters."""
        with self._lock:
            self._entries.clear()
            self.hit_count = 0
            self.miss_count = 0

    @property
    def size(self) -> int:
        """Return the number of cached modules."""
        with self._lock:
            return len(self._entries)

    @property
    def capacity(self) -> int:
        """Return the configured capacity."""
        return self._capacity
