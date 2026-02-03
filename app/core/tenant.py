# app/core/tenant.py
"""
Multi-tenancy middleware and utilities.
Provides tenant context injection for API requests.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Optional
from datetime import datetime

from fastapi import Request, HTTPException, Depends
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.deps import get_db
from app.domain.models import TenantAPIKey, Tenant

log = logging.getLogger(__name__)

# Header name for external API authentication
API_KEY_HEADER = "X-API-Key"


def hash_api_key(key: str) -> str:
    """Hash an API key using SHA256."""
    return hashlib.sha256(key.encode()).hexdigest()


async def get_tenant_from_api_key(api_key: str, db: Session) -> Optional[Tenant]:
    """
    Validate an API key and return the associated tenant.
    Returns None if key is invalid or inactive.
    """
    key_hash = hash_api_key(api_key)
    
    api_key_record = db.query(TenantAPIKey).filter(
        TenantAPIKey.key_hash == key_hash,
        TenantAPIKey.is_active == True
    ).first()
    
    if not api_key_record:
        return None
    
    # Check expiration
    if api_key_record.expires_at and api_key_record.expires_at < datetime.utcnow():
        return None
    
    # Update last used
    api_key_record.last_used_at = datetime.utcnow()
    db.commit()
    
    # Get tenant
    tenant = db.query(Tenant).filter(
        Tenant.id == api_key_record.tenant_id,
        Tenant.is_active == True
    ).first()
    
    return tenant


class TenantContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware to extract tenant context from requests.
    
    For internal users (JWT auth): tenant_id comes from user's tenant_id.
    For external API (API Key): tenant_id comes from the API key's tenant.
    """
    
    async def dispatch(self, request: Request, call_next):
        # Initialize tenant context as None
        request.state.tenant_id = None
        request.state.tenant = None
        
        # Check for API Key header (external API)
        api_key = request.headers.get(API_KEY_HEADER)
        if api_key:
            # We'll validate in the endpoint itself since we need DB session
            request.state.api_key = api_key
        
        response = await call_next(request)
        return response


async def get_current_tenant(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional[Tenant]:
    """
    Dependency to get the current tenant from request context.
    Works with both JWT (internal) and API Key (external) authentication.
    """
    # Try API Key first (external)
    api_key = getattr(request.state, "api_key", None)
    if api_key:
        tenant = await get_tenant_from_api_key(api_key, db)
        if tenant:
            request.state.tenant_id = tenant.id
            request.state.tenant = tenant
            return tenant
        else:
            raise HTTPException(status_code=401, detail="Invalid or expired API key")
    
    # For internal users, tenant comes from the user object (set by auth middleware)
    # This will be populated after user auth
    return getattr(request.state, "tenant", None)


async def require_tenant(
    request: Request,
    db: Session = Depends(get_db)
) -> Tenant:
    """
    Dependency that requires a valid tenant context.
    Raises 401 if no tenant is found.
    """
    tenant = await get_current_tenant(request, db)
    if not tenant:
        raise HTTPException(
            status_code=401,
            detail="Tenant context required. Provide X-API-Key header or authenticate as a user."
        )
    return tenant


def generate_api_key(prefix: str = "ak_live_") -> tuple[str, str]:
    """
    Generate a new API key.
    Returns (full_key, key_hash) tuple.
    The full key should be shown to the user once, then discarded.
    """
    import secrets
    random_part = secrets.token_urlsafe(32)
    full_key = f"{prefix}{random_part}"
    return full_key, hash_api_key(full_key)
