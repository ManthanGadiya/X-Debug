"""Unit tests for the content-addressed parse cache."""

from __future__ import annotations

import pytest
from app.analysis.model import ModuleAST
from app.analysis.parsers.cache import ParseCache
from app.projects.languages import Language


def _module(path: str = "a.py") -> ModuleAST:
    return ModuleAST(path=path, language=Language.PYTHON)


def test_miss_returns_none() -> None:
    """A lookup for an unseen source is a miss and returns ``None``."""
    cache = ParseCache(capacity=4)
    assert cache.get(Language.PYTHON, "a.py", "x = 1\n") is None
    assert cache.miss_count == 1
    assert cache.hit_count == 0
    assert cache.size == 0


def test_put_then_get_returns_same_object() -> None:
    """Storing a module and reading it back returns the identical object."""
    cache = ParseCache(capacity=4)
    module = _module()
    cache.put(Language.PYTHON, "a.py", "x = 1\n", module)
    assert cache.get(Language.PYTHON, "a.py", "x = 1\n") is module
    assert cache.hit_count == 1
    assert cache.miss_count == 0
    assert cache.size == 1


def test_changed_source_is_a_miss() -> None:
    """An edit to the source invalidates that file's cached module."""
    cache = ParseCache(capacity=4)
    cache.put(Language.PYTHON, "a.py", "x = 1\n", _module())
    assert cache.get(Language.PYTHON, "a.py", "x = 2\n") is None
    assert cache.size == 1


def test_different_path_is_a_miss() -> None:
    """The same source text under a different path is not shared."""
    cache = ParseCache(capacity=4)
    cache.put(Language.PYTHON, "a.py", "x = 1\n", _module())
    assert cache.get(Language.PYTHON, "b.py", "x = 1\n") is None


def test_lru_eviction_drops_least_recently_used() -> None:
    """The least-recently-used entry is evicted first past capacity."""
    cache = ParseCache(capacity=2)
    first = _module("a.py")
    cache.put(Language.PYTHON, "a.py", "a", first)
    cache.put(Language.PYTHON, "b.py", "b", _module("b.py"))
    # Touch "a.py" so "b.py" becomes the least-recently-used entry.
    assert cache.get(Language.PYTHON, "a.py", "a") is first
    cache.put(Language.PYTHON, "c.py", "c", _module("c.py"))
    assert cache.size == 2
    assert cache.get(Language.PYTHON, "b.py", "b") is None
    assert cache.get(Language.PYTHON, "a.py", "a") is first


def test_put_overwrite_moves_to_most_recent() -> None:
    """Re-storing a key refreshes its recency instead of evicting it."""
    cache = ParseCache(capacity=2)
    cache.put(Language.PYTHON, "a.py", "x", _module("a.py"))
    cache.put(Language.PYTHON, "b.py", "y", _module("b.py"))
    cache.put(Language.PYTHON, "a.py", "x", _module("a.py"))
    cache.put(Language.PYTHON, "c.py", "z", _module("c.py"))
    assert cache.get(Language.PYTHON, "a.py", "x") is not None
    assert cache.get(Language.PYTHON, "b.py", "y") is None


def test_clear_resets_entries_and_counters() -> None:
    """Clearing drops every entry and zeroes the hit/miss counters."""
    cache = ParseCache(capacity=4)
    cache.put(Language.PYTHON, "a.py", "x", _module())
    assert cache.get(Language.PYTHON, "a.py", "x") is not None
    cache.clear()
    assert cache.size == 0
    assert cache.hit_count == 0
    assert cache.miss_count == 0


def test_rejects_zero_capacity() -> None:
    """A cache must be able to hold at least one module."""
    with pytest.raises(ValueError):
        ParseCache(capacity=0)
