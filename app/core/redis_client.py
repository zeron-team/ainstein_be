# app/core/redis_client.py
"""
Redis Client for FERRO Protocol - Dopamine Layer (Caching)
Provides async Redis connection and caching utilities.
"""
import json
import hashlib
from typing import Optional, Any, Callable
from functools import wraps
import redis.asyncio as redis
from app.core.config import settings
import logging

log = logging.getLogger(__name__)

# Global Redis connection pool
_redis_pool: Optional[redis.Redis] = None


async def get_redis() -> redis.Redis:
    """Get or create async Redis connection."""
    global _redis_pool
    if _redis_pool is None:
        try:
            _redis_pool = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
            # Test connection
            await _redis_pool.ping()
            log.info("[Redis] Connected successfully to Dopamine Layer")
        except Exception as e:
            log.warning(f"[Redis] Connection failed: {e}. Caching disabled.")
            _redis_pool = None
    return _redis_pool


async def close_redis():
    """Close Redis connection on shutdown."""
    global _redis_pool
    if _redis_pool:
        await _redis_pool.close()
        _redis_pool = None
        log.info("[Redis] Connection closed")


def cache_key(*args, **kwargs) -> str:
    """Generate a cache key from arguments."""
    key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
    return hashlib.md5(key_data.encode()).hexdigest()


async def cache_get(key: str) -> Optional[str]:
    """Get value from cache."""
    r = await get_redis()
    if r:
        try:
            return await r.get(key)
        except Exception as e:
            log.warning(f"[Redis] Cache get failed: {e}")
    return None


async def cache_set(key: str, value: str, ttl_seconds: int = 3600) -> bool:
    """Set value in cache with TTL."""
    r = await get_redis()
    if r:
        try:
            await r.setex(key, ttl_seconds, value)
            return True
        except Exception as e:
            log.warning(f"[Redis] Cache set failed: {e}")
    return False


async def cache_delete(pattern: str) -> int:
    """Delete keys matching pattern."""
    r = await get_redis()
    if r:
        try:
            keys = await r.keys(pattern)
            if keys:
                return await r.delete(*keys)
        except Exception as e:
            log.warning(f"[Redis] Cache delete failed: {e}")
    return 0


async def rate_limit_check(key: str, max_requests: int = 10, window_seconds: int = 60) -> bool:
    """
    Check rate limit for a key.
    Returns True if allowed, False if rate limited.
    """
    r = await get_redis()
    if not r:
        return True  # Allow if Redis unavailable
    
    try:
        current = await r.incr(key)
        if current == 1:
            await r.expire(key, window_seconds)
        return current <= max_requests
    except Exception as e:
        log.warning(f"[Redis] Rate limit check failed: {e}")
        return True


def cached_response(prefix: str, ttl_seconds: int = 3600):
    """
    Decorator to cache function responses.
    Usage:
        @cached_response("epc", ttl_seconds=1800)
        async def generate_epc(hce_id: str, user_id: str):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            key = f"{prefix}:{cache_key(*args, **kwargs)}"
            
            # Try to get from cache
            cached = await cache_get(key)
            if cached:
                log.debug(f"[Redis] Cache HIT for {prefix}")
                return json.loads(cached)
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Cache result (only if not None)
            if result is not None:
                await cache_set(key, json.dumps(result, default=str), ttl_seconds)
                log.debug(f"[Redis] Cache SET for {prefix}")
            
            return result
        return wrapper
    return decorator


# Health check for Redis
async def redis_health() -> dict:
    """Check Redis health status."""
    r = await get_redis()
    if r:
        try:
            await r.ping()
            info = await r.info("memory")
            return {
                "status": "ok",
                "message": "Redis connected",
                "used_memory": info.get("used_memory_human", "unknown")
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "disabled", "message": "Redis not configured"}
