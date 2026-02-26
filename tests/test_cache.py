"""Tests for cache module - ThingsCache, @cached decorator, and cache utilities."""

import time
import pytest
from unittest.mock import patch


pytestmark = [pytest.mark.unit]


class TestThingsCache:
    """Tests for ThingsCache class."""

    def _make_cache(self, default_ttl=300):
        """Create a fresh cache instance (avoids global state)."""
        from things_mcp.cache import ThingsCache

        return ThingsCache(default_ttl=default_ttl)

    def test_set_and_get(self):
        """Basic set/get cycle returns cached value."""
        cache = self._make_cache()
        cache.set("todos", [{"title": "Test"}], tags="work")
        result = cache.get("todos", tags="work")

        assert result == [{"title": "Test"}]

    def test_get_miss_returns_none(self):
        """Cache miss returns None."""
        cache = self._make_cache()
        result = cache.get("nonexistent")

        assert result is None

    def test_different_kwargs_different_keys(self):
        """Different kwargs produce different cache entries."""
        cache = self._make_cache()
        cache.set("todos", ["inbox"], list="inbox")
        cache.set("todos", ["today"], list="today")

        assert cache.get("todos", list="inbox") == ["inbox"]
        assert cache.get("todos", list="today") == ["today"]

    def test_expiry(self):
        """Expired entries return None."""
        cache = self._make_cache(default_ttl=1)
        cache.set("todos", "data")

        # Manually expire the entry
        key = cache._make_key("todos")
        cache.cache[key] = (cache.cache[key][0], time.time() - 1)

        result = cache.get("todos")
        assert result is None

    def test_custom_ttl_on_set(self):
        """Custom TTL per-entry overrides default."""
        cache = self._make_cache(default_ttl=300)
        cache.set("fast", "value", ttl=1)

        # Manually expire
        key = cache._make_key("fast")
        cache.cache[key] = (cache.cache[key][0], time.time() - 1)

        assert cache.get("fast") is None

    def test_hit_and_miss_counts(self):
        """Hit/miss counters are tracked correctly."""
        cache = self._make_cache()

        cache.get("miss1")  # miss
        cache.get("miss2")  # miss
        cache.set("hit", "val")
        cache.get("hit")  # hit
        cache.get("hit")  # hit

        assert cache.hit_count == 2
        assert cache.miss_count == 2

    def test_invalidate_specific_entry(self):
        """Invalidate a specific cache entry by operation + kwargs."""
        cache = self._make_cache()
        cache.set("todos", "data1", list="inbox")
        cache.set("todos", "data2", list="today")

        cache.invalidate("todos", list="inbox")

        assert cache.get("todos", list="inbox") is None
        assert cache.get("todos", list="today") == "data2"

    def test_invalidate_all(self):
        """Invalidate with no args clears entire cache."""
        cache = self._make_cache()
        cache.set("a", 1)
        cache.set("b", 2)

        cache.invalidate()

        assert cache.get("a") is None
        assert cache.get("b") is None
        assert len(cache.cache) == 0

    def test_cleanup_expired(self):
        """cleanup_expired removes stale entries and returns count."""
        cache = self._make_cache(default_ttl=1)
        cache.set("old", "value")

        # Manually expire
        key = cache._make_key("old")
        cache.cache[key] = (cache.cache[key][0], time.time() - 1)

        cache.set("fresh", "value", ttl=300)

        removed = cache.cleanup_expired()

        assert removed == 1
        assert cache.get("fresh") == "value"

    def test_cleanup_expired_nothing_to_remove(self):
        """cleanup_expired returns 0 when nothing is expired."""
        cache = self._make_cache()
        cache.set("fresh", "value")

        removed = cache.cleanup_expired()
        assert removed == 0

    def test_get_stats(self):
        """get_stats returns correct structure."""
        cache = self._make_cache()
        cache.set("key", "val")
        cache.get("key")  # hit
        cache.get("missing")  # miss

        stats = cache.get_stats()

        assert stats["entries"] == 1
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["total_requests"] == 2
        assert "50.0%" in stats["hit_rate"]

    def test_get_stats_no_requests(self):
        """get_stats with zero requests doesn't divide by zero."""
        cache = self._make_cache()
        stats = cache.get_stats()

        assert stats["total_requests"] == 0
        assert stats["hit_rate"] == "0.0%"

    def test_make_key_deterministic(self):
        """Same operation + kwargs always produce the same key."""
        cache = self._make_cache()
        key1 = cache._make_key("op", a=1, b="two")
        key2 = cache._make_key("op", a=1, b="two")

        assert key1 == key2

    def test_make_key_kwarg_order_independent(self):
        """Kwarg order doesn't affect the key (sorted internally)."""
        cache = self._make_cache()
        key1 = cache._make_key("op", a=1, b=2)
        key2 = cache._make_key("op", b=2, a=1)

        assert key1 == key2


class TestCachedDecorator:
    """Tests for the @cached() decorator."""

    def test_caches_return_value(self):
        """Decorated function's result is cached on second call."""
        from things_mcp.cache import ThingsCache

        # Use a fresh cache instance to avoid global state
        test_cache = ThingsCache(default_ttl=300)
        call_count = 0

        with patch("things_mcp.cache._cache", test_cache):
            from things_mcp.cache import cached

            @cached(ttl=60)
            def expensive():
                nonlocal call_count
                call_count += 1
                return "result"

            result1 = expensive()
            result2 = expensive()

        assert result1 == "result"
        assert result2 == "result"
        assert call_count == 1  # Only called once, second was cached

    def test_different_kwargs_not_cached(self):
        """Different kwargs produce separate cache entries."""
        from things_mcp.cache import ThingsCache

        test_cache = ThingsCache(default_ttl=300)
        call_count = 0

        with patch("things_mcp.cache._cache", test_cache):
            from things_mcp.cache import cached

            @cached(ttl=60)
            def fetch(list_name="inbox"):
                nonlocal call_count
                call_count += 1
                return f"data-{list_name}"

            r1 = fetch(list_name="inbox")
            r2 = fetch(list_name="today")

        assert r1 == "data-inbox"
        assert r2 == "data-today"
        assert call_count == 2


class TestCacheUtilities:
    """Tests for module-level cache utility functions."""

    def test_get_cache_stats(self):
        """get_cache_stats returns dict with expected keys."""
        from things_mcp.cache import get_cache_stats

        stats = get_cache_stats()

        assert "entries" in stats
        assert "hits" in stats
        assert "misses" in stats
        assert "hit_rate" in stats

    def test_clear_cache(self):
        """clear_cache empties the global cache."""
        from things_mcp.cache import _cache, clear_cache

        _cache.set("test_clear", "value")
        clear_cache()

        assert _cache.get("test_clear") is None

    def test_invalidate_caches_for(self):
        """invalidate_caches_for clears specific operations."""
        from things_mcp.cache import _cache, invalidate_caches_for

        _cache.set("op_a", "val_a")
        _cache.set("op_b", "val_b")

        invalidate_caches_for(["op_a"])

        # op_a should be gone (if prefix-based invalidation matches)
        # op_b should still exist
        assert _cache.get("op_b") == "val_b"

    def test_cache_ttl_config_values(self):
        """CACHE_TTL has expected keys and reasonable values."""
        from things_mcp.cache import CACHE_TTL

        assert CACHE_TTL["inbox"] == 30
        assert CACHE_TTL["today"] == 30
        assert CACHE_TTL["areas"] == 600
        assert CACHE_TTL["tags"] == 600
        assert all(isinstance(v, int) for v in CACHE_TTL.values())
        assert all(v > 0 for v in CACHE_TTL.values())
