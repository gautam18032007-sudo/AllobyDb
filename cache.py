"""
cache.py — Intelligent caching layer with TTL support

Provides:
- In-memory LRU cache for query results
- TTL-based cache expiration
- Cache statistics and monitoring
- Thread-safe operations
"""

import time
import logging
import threading
from collections import OrderedDict
from functools import wraps
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)

class TTLCache:
    """Thread-safe LRU cache with TTL support."""
    
    def __init__(self, max_size: int = 100, ttl_seconds: int = 300):
        self.max_size = max_size
        self.ttl = ttl_seconds
        self.cache = OrderedDict()
        self.timestamps = {}
        self.hits = 0
        self.misses = 0
        self._lock = threading.Lock()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        with self._lock:
            if key in self.cache:
                # Check if expired
                if time.time() - self.timestamps[key] > self.ttl:
                    self._remove(key)
                    self.misses += 1
                    return None
                
                # Move to end (most recently used)
                value = self.cache.pop(key)
                self.cache[key] = value
                self.hits += 1
                return value
            
            self.misses += 1
            return None
    
    def set(self, key: str, value: Any) -> None:
        """Store value in cache."""
        with self._lock:
            if key in self.cache:
                self.cache.pop(key)
            elif len(self.cache) >= self.max_size:
                # Remove oldest item
                oldest_key = next(iter(self.cache))
                self._remove(oldest_key)
            
            self.cache[key] = value
            self.timestamps[key] = time.time()
    
    def invalidate(self, key: str) -> bool:
        """Remove specific key from cache."""
        with self._lock:
            if key in self.cache:
                self._remove(key)
                return True
            return False
    
    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self.cache.clear()
            self.timestamps.clear()
            self.hits = 0
            self.misses = 0
    
    def get_stats(self) -> dict:
        """Return cache statistics."""
        with self._lock:
            total = self.hits + self.misses
            hit_rate = (self.hits / total * 100) if total > 0 else 0
            return {
                "size": len(self.cache),
                "max_size": self.max_size,
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": f"{hit_rate:.1f}%",
                "ttl_seconds": self.ttl
            }
    
    def _remove(self, key: str) -> None:
        """Internal method to remove a key."""
        self.cache.pop(key, None)
        self.timestamps.pop(key, None)


# Global cache instances
_query_cache = TTLCache(max_size=200, ttl_seconds=300)  # 5 min TTL
_stats_cache = TTLCache(max_size=10, ttl_seconds=60)    # 1 min TTL


def cache_query(ttl: int = 300, key_prefix: str = ""):
    """Decorator to cache function results based on query content."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{key_prefix}:{str(args)}:{str(kwargs)}"
            
            # Try to get from cache
            cached = _query_cache.get(cache_key)
            if cached is not None:
                log.debug(f"Cache HIT for {func.__name__}")
                return cached
            
            # Execute and cache result
            log.debug(f"Cache MISS for {func.__name__}")
            result = func(*args, **kwargs)
            _query_cache.set(cache_key, result)
            return result
        
        # Expose cache methods
        wrapper.invalidate_cache = lambda key: _query_cache.invalidate(f"{key_prefix}:{key}")
        wrapper.get_cache_stats = _query_cache.get_stats
        wrapper.clear_cache = _query_cache.clear
        
        return wrapper
    return decorator


def cache_stats(ttl: int = 60):
    """Decorator to cache database statistics."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"stats:{func.__name__}"
            cached = _stats_cache.get(cache_key)
            if cached is not None:
                return cached
            
            result = func(*args, **kwargs)
            _stats_cache.set(cache_key, result)
            return result
        
        wrapper.clear_cache = _stats_cache.clear
        return wrapper
    return decorator


def invalidate_cache_key(key: str) -> bool:
    """Invalidate a specific cache key."""
    return _query_cache.invalidate(key)


def clear_all_caches() -> None:
    """Clear all caches."""
    _query_cache.clear()
    _stats_cache.clear()
    log.info("All caches cleared")


def get_cache_stats() -> dict:
    """Get statistics for all caches."""
    return {
        "query_cache": _query_cache.get_stats(),
        "stats_cache": _stats_cache.get_stats()
    }
