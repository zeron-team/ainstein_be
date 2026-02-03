# app/services/redis_cache.py
"""
FERRO D2 v3.0.0 - Redis Caching Layer

Provides:
- Semantic query caching with TTL
- Namespace isolation per tenant
- Cache invalidation patterns
- Health checks

FERRO D2 Rules:
- TTL obligatorio en todas las keys
- Namespaces por tenant_id
- Fire & forget para writes (no bloquean)
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Optional, Union
from datetime import timedelta

from app.core.config import settings

log = logging.getLogger(__name__)


class RedisCache:
    """
    FERRO D2 compliant Redis cache service.
    
    Namespaces:
    - ferro:cache:{tenant_id}:{key_type}:{hash}
    - ferro:session:{session_id}
    - ferro:ratelimit:{tenant_id}:{user_id}
    """
    
    # Default TTLs (seconds)
    TTL_QUERY_CACHE = 3600        # 1 hour for query results
    TTL_EPC_CACHE = 1800          # 30 min for EPC results
    TTL_SESSION = 86400           # 24 hours for sessions
    TTL_RATELIMIT = 60            # 1 min for rate limit windows
    
    # Namespace prefixes
    NS_CACHE = "ferro:cache"
    NS_SESSION = "ferro:session"
    NS_RATELIMIT = "ferro:ratelimit"
    
    def __init__(self):
        self._client = None
        self._initialized = False
        self._available = False
    
    def _initialize(self):
        """Lazy initialization of Redis connection."""
        if self._initialized:
            return
        
        try:
            import redis.asyncio as redis
            
            redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
            self._client = redis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            self._available = True
            self._initialized = True
            log.info("[RedisCache] Connected to Redis at %s", redis_url)
            
        except ImportError:
            log.warning("[RedisCache] redis package not installed")
            self._initialized = True
            self._available = False
        except Exception as e:
            log.warning("[RedisCache] Failed to connect: %s", e)
            self._initialized = True
            self._available = False
    
    @property
    def client(self):
        if not self._initialized:
            self._initialize()
        return self._client
    
    @property
    def is_available(self) -> bool:
        if not self._initialized:
            self._initialize()
        return self._available
    
    # =========================================================================
    # Key Generation
    # =========================================================================
    
    def _hash_key(self, data: str) -> str:
        """Generate a short hash for cache keys."""
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def _make_cache_key(self, tenant_id: str, key_type: str, identifier: str) -> str:
        """
        Generate namespaced cache key.
        
        Args:
            tenant_id: Tenant UUID
            key_type: Type of cached data (query, epc, hce)
            identifier: Unique identifier or hash
        """
        return f"{self.NS_CACHE}:{tenant_id}:{key_type}:{identifier}"
    
    def query_cache_key(self, tenant_id: str, query: str, context_hash: str = "") -> str:
        """Generate cache key for semantic query results."""
        combined = f"{query}:{context_hash}"
        return self._make_cache_key(tenant_id, "query", self._hash_key(combined))
    
    def epc_cache_key(self, tenant_id: str, patient_id: str, hce_hash: str) -> str:
        """Generate cache key for EPC results."""
        combined = f"{patient_id}:{hce_hash}"
        return self._make_cache_key(tenant_id, "epc", self._hash_key(combined))
    
    # =========================================================================
    # Cache Operations
    # =========================================================================
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Returns None if not found or Redis unavailable.
        """
        if not self.is_available:
            return None
        
        try:
            value = await self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            log.warning("[RedisCache] GET error: %s", e)
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = TTL_QUERY_CACHE,
    ) -> bool:
        """
        Set value in cache with TTL.
        
        FERRO D2 Rule: TTL is MANDATORY.
        
        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl: Time-to-live in seconds (default: 1 hour)
        
        Returns:
            True if successful, False otherwise
        """
        if not self.is_available:
            return False
        
        try:
            serialized = json.dumps(value, default=str)
            await self.client.setex(key, ttl, serialized)
            return True
        except Exception as e:
            log.warning("[RedisCache] SET error: %s", e)
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        if not self.is_available:
            return False
        
        try:
            await self.client.delete(key)
            return True
        except Exception as e:
            log.warning("[RedisCache] DELETE error: %s", e)
            return False
    
    async def invalidate_tenant(self, tenant_id: str) -> int:
        """
        Invalidate all cache entries for a tenant.
        
        Returns number of keys deleted.
        """
        if not self.is_available:
            return 0
        
        try:
            pattern = f"{self.NS_CACHE}:{tenant_id}:*"
            keys = []
            async for key in self.client.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                deleted = await self.client.delete(*keys)
                log.info("[RedisCache] Invalidated %d keys for tenant %s", deleted, tenant_id)
                return deleted
            return 0
        except Exception as e:
            log.warning("[RedisCache] Invalidate error: %s", e)
            return 0
    
    # =========================================================================
    # Rate Limiting
    # =========================================================================
    
    async def check_rate_limit(
        self,
        tenant_id: str,
        user_id: str,
        limit: int = 60,
        window: int = 60,
    ) -> tuple[bool, int]:
        """
        Check and increment rate limit counter.
        
        Args:
            tenant_id: Tenant UUID
            user_id: User UUID
            limit: Max requests per window
            window: Window size in seconds
        
        Returns:
            Tuple of (allowed: bool, remaining: int)
        """
        if not self.is_available:
            return True, limit  # Fail open if Redis unavailable
        
        key = f"{self.NS_RATELIMIT}:{tenant_id}:{user_id}"
        
        try:
            current = await self.client.incr(key)
            
            if current == 1:
                # First request in window, set expiry
                await self.client.expire(key, window)
            
            remaining = max(0, limit - current)
            allowed = current <= limit
            
            return allowed, remaining
        except Exception as e:
            log.warning("[RedisCache] Rate limit error: %s", e)
            return True, limit
    
    # =========================================================================
    # Health Check
    # =========================================================================
    
    async def health_check(self) -> dict:
        """
        Check Redis health status.
        
        Returns dict with status and info.
        """
        if not self.is_available:
            return {
                "status": "unavailable",
                "message": "Redis client not initialized",
            }
        
        try:
            await self.client.ping()
            info = await self.client.info("server")
            return {
                "status": "ok",
                "redis_version": info.get("redis_version", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
            }


# ============================================================================
# Singleton
# ============================================================================

_redis_cache: Optional[RedisCache] = None


def get_redis_cache() -> RedisCache:
    """Get singleton Redis cache instance."""
    global _redis_cache
    if _redis_cache is None:
        _redis_cache = RedisCache()
    return _redis_cache
