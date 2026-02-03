# app/core/tenant_context.py
"""
FERRO D2 v3.0.0 - Tenant Context Middleware

Provides:
- SET LOCAL app.tenant_id per request
- SET LOCAL app.user_id per request
- Context manager for tenant-scoped transactions
- RLS enforcement at database level

Usage:
    @app.middleware("http")
    async def tenant_middleware(request: Request, call_next):
        async with tenant_context(db, request.state.tenant_id, request.state.user_id):
            return await call_next(request)
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Optional, AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

log = logging.getLogger(__name__)


class TenantContext:
    """
    Context manager for tenant-scoped database operations.
    
    FERRO D2 Rule: All multi-tenant queries MUST run inside TenantContext.
    This sets the PostgreSQL GUC variables that RLS policies use.
    """
    
    def __init__(self, session, tenant_id: str, user_id: Optional[str] = None):
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id
        self._previous_tenant = None
        self._previous_user = None
    
    async def __aenter__(self):
        """Set tenant context at start of scope."""
        try:
            # Set tenant_id (required)
            await self.session.execute(
                text("SET LOCAL app.tenant_id = :tid"),
                {"tid": self.tenant_id}
            )
            
            # Set user_id (optional)
            if self.user_id:
                await self.session.execute(
                    text("SET LOCAL app.user_id = :uid"),
                    {"uid": self.user_id}
                )
            
            log.debug("[TenantContext] Set tenant=%s user=%s", self.tenant_id, self.user_id)
            
        except Exception as e:
            log.warning("[TenantContext] Failed to set context: %s", e)
            # Don't fail - RLS will use NULL tenant which should deny access
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context automatically cleared when connection returns to pool."""
        # SET LOCAL is automatically reset at end of transaction
        # No cleanup needed
        pass


@asynccontextmanager
async def tenant_context(
    session,
    tenant_id: str,
    user_id: Optional[str] = None
) -> AsyncGenerator[TenantContext, None]:
    """
    Async context manager for tenant-scoped operations.
    
    Usage:
        async with tenant_context(db, tenant_id, user_id):
            result = await db.execute(select(Patient))
            # Only returns patients for this tenant due to RLS
    """
    ctx = TenantContext(session, tenant_id, user_id)
    try:
        await ctx.__aenter__()
        yield ctx
    finally:
        await ctx.__aexit__(None, None, None)


def set_tenant_context_sync(connection, tenant_id: str, user_id: Optional[str] = None):
    """
    Synchronous version for SQLAlchemy sync sessions.
    
    Usage with sync session:
        with db.begin():
            set_tenant_context_sync(db.connection(), tenant_id, user_id)
            result = db.execute(select(Patient))
    """
    try:
        connection.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tenant_id})
        if user_id:
            connection.execute(text("SET LOCAL app.user_id = :uid"), {"uid": user_id})
        log.debug("[TenantContext] Sync set tenant=%s user=%s", tenant_id, user_id)
    except Exception as e:
        log.warning("[TenantContext] Failed to set sync context: %s", e)


# FastAPI Dependency for injecting tenant context
async def get_tenant_context(
    request,
    db,
) -> TenantContext:
    """
    FastAPI dependency that creates TenantContext from request.
    
    Expects request.state to have:
    - tenant_id: str (from auth middleware)
    - user_id: str (from auth middleware)
    
    Usage:
        @router.get("/items")
        async def list_items(
            db: Session = Depends(get_db),
            ctx: TenantContext = Depends(get_tenant_context),
        ):
            # RLS automatically filters by tenant
            return db.query(Item).all()
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    user_id = getattr(request.state, "user_id", None)
    
    if not tenant_id:
        log.warning("[TenantContext] No tenant_id in request.state")
        # Return a context with empty tenant - RLS will deny access
        tenant_id = ""
    
    ctx = TenantContext(db, tenant_id, user_id)
    await ctx.__aenter__()
    return ctx
