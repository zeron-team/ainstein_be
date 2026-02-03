# app/routers/tenants.py
"""
Admin API router for tenant management.
Only accessible by admin users.
"""
from __future__ import annotations

import uuid
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.domain.models import User, Tenant, TenantAPIKey
from app.core.tenant import generate_api_key, hash_api_key

log = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/tenants", tags=["Admin - Tenants"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

# Available permission scopes
AVAILABLE_SCOPES = [
    "read_patients",      # Can read patient data
    "write_patients",     # Can create/update patients
    "read_admissions",    # Can read admission data
    "write_admissions",   # Can create/update admissions
    "read_epc",           # Can read generated EPCs
    "generate_epc",       # Can request EPC generation
    "webhook",            # Can receive webhook notifications
]

class TenantCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=50, pattern="^[a-z0-9_]+$")
    name: str = Field(..., min_length=2, max_length=160)
    contact_email: Optional[str] = None
    logo_url: Optional[str] = None
    
    # Integration type
    integration_type: str = Field(default="outbound", pattern="^(inbound|outbound|bidirectional)$")
    
    # Inbound settings (we consume from them)
    external_endpoint: Optional[str] = None
    external_token: Optional[str] = None
    external_auth_type: str = Field(default="bearer", pattern="^(bearer|api_key|basic|oauth2)$")
    external_headers: Optional[str] = None  # JSON string
    
    # Outbound settings (they consume from us)
    allowed_scopes: str = Field(default="read_patients,read_epc")
    
    # General
    webhook_url: Optional[str] = None
    webhook_secret: Optional[str] = None
    api_rate_limit: int = 100
    notes: Optional[str] = None


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    contact_email: Optional[str] = None
    logo_url: Optional[str] = None
    is_active: Optional[bool] = None
    
    # Integration type
    integration_type: Optional[str] = None
    
    # Inbound settings
    external_endpoint: Optional[str] = None
    external_token: Optional[str] = None
    external_auth_type: Optional[str] = None
    external_headers: Optional[str] = None
    
    # Outbound settings
    allowed_scopes: Optional[str] = None
    
    # General
    webhook_url: Optional[str] = None
    webhook_secret: Optional[str] = None
    api_rate_limit: Optional[int] = None
    notes: Optional[str] = None


class TenantResponse(BaseModel):
    id: str
    code: str
    name: str
    contact_email: Optional[str]
    logo_url: Optional[str]
    is_active: bool
    created_at: Optional[datetime]
    api_key_count: int = 0
    
    # Integration type
    integration_type: str
    
    # Inbound settings (hide token for security - only show if exists)
    external_endpoint: Optional[str]
    external_auth_type: Optional[str]
    has_external_token: bool = False  # Don't expose actual token
    
    # Outbound settings
    allowed_scopes: Optional[str]
    allowed_scopes_list: List[str] = []  # Parsed list for frontend
    
    # General
    webhook_url: Optional[str]
    has_webhook_secret: bool = False  # Don't expose actual secret
    api_rate_limit: int
    notes: Optional[str]

    class Config:
        from_attributes = True


class APIKeyCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    expires_at: Optional[datetime] = None


class APIKeyResponse(BaseModel):
    id: str
    tenant_id: str
    key_prefix: str
    name: Optional[str]
    is_active: bool
    created_at: Optional[datetime]
    last_used_at: Optional[datetime]
    expires_at: Optional[datetime]
    # Only returned on creation
    full_key: Optional[str] = None

    class Config:
        from_attributes = True


# =============================================================================
# HELPER: Check admin role
# =============================================================================

def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Dependency that requires admin role. User is a dict from get_current_user."""
    user_role = user.get("role", "")
    if not user_role or user_role.lower() != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def build_tenant_response(tenant: Tenant, api_key_count: int = 0) -> TenantResponse:
    """Build a TenantResponse from a Tenant model, handling all new fields."""
    scopes = tenant.allowed_scopes or "read_patients,read_epc"
    return TenantResponse(
        id=tenant.id,
        code=tenant.code,
        name=tenant.name,
        contact_email=tenant.contact_email,
        logo_url=tenant.logo_url,
        is_active=tenant.is_active,
        created_at=tenant.created_at,
        api_key_count=api_key_count,
        # Integration type
        integration_type=tenant.integration_type or "outbound",
        # Inbound settings
        external_endpoint=tenant.external_endpoint,
        external_auth_type=tenant.external_auth_type,
        has_external_token=bool(tenant.external_token),
        # Outbound settings
        allowed_scopes=scopes,
        allowed_scopes_list=scopes.split(",") if scopes else [],
        # General
        webhook_url=tenant.webhook_url,
        has_webhook_secret=bool(tenant.webhook_secret),
        api_rate_limit=tenant.api_rate_limit or 100,
        notes=tenant.notes,
    )


# =============================================================================
# TENANT CRUD ENDPOINTS
# =============================================================================

@router.get(
    "",
    response_model=List[TenantResponse],
    summary="List all tenants",
)
async def list_tenants(
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    include_inactive: bool = Query(default=False),
):
    """List all tenants (admin only)."""
    query = db.query(Tenant)
    if not include_inactive:
        query = query.filter(Tenant.is_active == True)
    
    tenants = query.order_by(Tenant.created_at.desc()).all()
    
    result = []
    for t in tenants:
        api_key_count = db.query(TenantAPIKey).filter(
            TenantAPIKey.tenant_id == t.id,
            TenantAPIKey.is_active == True
        ).count()
        result.append(build_tenant_response(t, api_key_count))
    
    return result


@router.post(
    "",
    response_model=TenantResponse,
    summary="Create a new tenant",
)
async def create_tenant(
    data: TenantCreate,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a new tenant (admin only)."""
    # Check for duplicate code
    existing = db.query(Tenant).filter(Tenant.code == data.code).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Tenant code '{data.code}' already exists")
    
    tenant = Tenant(
        id=str(uuid.uuid4()),
        code=data.code,
        name=data.name,
        contact_email=data.contact_email,
        logo_url=data.logo_url,
        is_active=True,
        created_at=datetime.utcnow(),
        # Integration type
        integration_type=data.integration_type,
        # Inbound settings
        external_endpoint=data.external_endpoint,
        external_token=data.external_token,
        external_auth_type=data.external_auth_type,
        external_headers=data.external_headers,
        # Outbound settings
        allowed_scopes=data.allowed_scopes,
        # General
        webhook_url=data.webhook_url,
        webhook_secret=data.webhook_secret,
        api_rate_limit=data.api_rate_limit,
        notes=data.notes,
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    
    log.info(f"Tenant created: {tenant.code} (type={tenant.integration_type}) by user {user.get('username')}")
    
    return build_tenant_response(tenant, api_key_count=0)


@router.get(
    "/{tenant_id}",
    response_model=TenantResponse,
    summary="Get tenant by ID",
)
async def get_tenant(
    tenant_id: str,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get a specific tenant by ID (admin only)."""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    api_key_count = db.query(TenantAPIKey).filter(
        TenantAPIKey.tenant_id == tenant.id,
        TenantAPIKey.is_active == True
    ).count()
    
    return build_tenant_response(tenant, api_key_count)


@router.patch(
    "/{tenant_id}",
    response_model=TenantResponse,
    summary="Update tenant",
)
async def update_tenant(
    tenant_id: str,
    data: TenantUpdate,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update a tenant (admin only)."""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(tenant, key, value)
    
    db.commit()
    db.refresh(tenant)
    
    api_key_count = db.query(TenantAPIKey).filter(
        TenantAPIKey.tenant_id == tenant.id,
        TenantAPIKey.is_active == True
    ).count()
    
    return build_tenant_response(tenant, api_key_count)


@router.delete(
    "/{tenant_id}",
    summary="Deactivate tenant",
)
async def delete_tenant(
    tenant_id: str,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Deactivate a tenant (soft delete, admin only)."""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    tenant.is_active = False
    db.commit()
    
    log.info(f"Tenant deactivated: {tenant.code} by user {user.username}")
    
    return {"status": "deactivated", "tenant_id": tenant_id}


# =============================================================================
# API KEY MANAGEMENT
# =============================================================================

@router.get(
    "/{tenant_id}/api-keys",
    response_model=List[APIKeyResponse],
    summary="List API keys for tenant",
)
async def list_api_keys(
    tenant_id: str,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all API keys for a tenant (admin only)."""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    keys = db.query(TenantAPIKey).filter(
        TenantAPIKey.tenant_id == tenant_id
    ).order_by(TenantAPIKey.created_at.desc()).all()
    
    return [
        APIKeyResponse(
            id=k.id,
            tenant_id=k.tenant_id,
            key_prefix=k.key_prefix or "",
            name=k.name,
            is_active=k.is_active,
            created_at=k.created_at,
            last_used_at=k.last_used_at,
            expires_at=k.expires_at,
        )
        for k in keys
    ]


@router.post(
    "/{tenant_id}/api-keys",
    response_model=APIKeyResponse,
    summary="Generate new API key",
)
async def create_api_key(
    tenant_id: str,
    data: APIKeyCreate,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Generate a new API key for a tenant (admin only). Returns the full key ONCE."""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Generate key with tenant-specific prefix
    prefix = f"ak_{tenant.code}_"
    full_key, key_hash = generate_api_key(prefix=prefix)
    
    api_key = TenantAPIKey(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        key_hash=key_hash,
        key_prefix=full_key[:len(prefix) + 4],  # prefix + first 4 chars of random part
        name=data.name,
        is_active=True,
        created_at=datetime.utcnow(),
        expires_at=data.expires_at,
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    
    log.info(f"API key generated for tenant {tenant.code} by user {user.username}")
    
    return APIKeyResponse(
        id=api_key.id,
        tenant_id=api_key.tenant_id,
        key_prefix=api_key.key_prefix or "",
        name=api_key.name,
        is_active=api_key.is_active,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
        expires_at=api_key.expires_at,
        full_key=full_key,  # Only returned on creation!
    )


@router.delete(
    "/{tenant_id}/api-keys/{key_id}",
    summary="Revoke API key",
)
async def revoke_api_key(
    tenant_id: str,
    key_id: str,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Revoke an API key (admin only)."""
    api_key = db.query(TenantAPIKey).filter(
        TenantAPIKey.id == key_id,
        TenantAPIKey.tenant_id == tenant_id
    ).first()
    
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    api_key.is_active = False
    db.commit()
    
    log.info(f"API key revoked: {api_key.key_prefix} by user {user.get('username')}")
    
    return {"status": "revoked", "key_id": key_id}


# =============================================================================
# TENANT CONFIGURATION & TESTING
# =============================================================================

@router.get(
    "/config/available-scopes",
    summary="Get available permission scopes",
)
async def get_available_scopes(
    user: dict = Depends(require_admin),
):
    """Get list of available permission scopes for outbound integrations."""
    return {
        "scopes": [
            {"id": s, "label": s.replace("_", " ").title()}
            for s in AVAILABLE_SCOPES
        ]
    }


@router.post(
    "/{tenant_id}/test-connection",
    summary="Test tenant HCE connection",
)
async def test_tenant_connection(
    tenant_id: str,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Test the connection to a tenant's HCE system.
    Validates that the external_endpoint and external_token are working.
    """
    import httpx
    import json
    
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Check if tenant has inbound config
    if tenant.integration_type not in ("inbound", "bidirectional"):
        return {
            "success": False,
            "tenant_code": tenant.code,
            "error": "Este tenant no tiene configuración de integración entrante (HCE)",
            "stage": "config"
        }
    
    if not tenant.external_endpoint:
        return {
            "success": False,
            "tenant_code": tenant.code,
            "error": "No hay endpoint externo configurado",
            "stage": "config"
        }
    
    if not tenant.external_token:
        return {
            "success": False,
            "tenant_code": tenant.code,
            "error": "No hay token externo configurado",
            "stage": "config"
        }
    
    # Parse extra config
    extra_config = {}
    if tenant.external_headers:
        try:
            extra_config = json.loads(tenant.external_headers)
        except json.JSONDecodeError:
            pass
    
    http_method = extra_config.get("http_method", "GET").upper()
    app_name = extra_config.get("app", "AInstein")
    api_key = extra_config.get("api_key", "")
    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Token": tenant.external_token,
    }
    
    timeout = httpx.Timeout(10.0, connect=5.0)
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.request(
                http_method,
                tenant.external_endpoint,
                json={
                    "aplicacion": app_name,
                    "apiKey": api_key,
                    "operacion": "ping",
                    "filtro": {},
                },
                headers=headers,
            )
            
            return {
                "success": True,
                "tenant_code": tenant.code,
                "endpoint": tenant.external_endpoint,
                "http_status": r.status_code,
                "response_preview": r.text[:300] if r.text else None,
                "message": "Conexión establecida correctamente"
            }
            
    except httpx.ConnectError as e:
        return {
            "success": False,
            "tenant_code": tenant.code,
            "endpoint": tenant.external_endpoint,
            "error": f"No se pudo conectar: {str(e)}",
            "stage": "connection"
        }
    except httpx.TimeoutException:
        return {
            "success": False,
            "tenant_code": tenant.code,
            "endpoint": tenant.external_endpoint,
            "error": "Timeout: el servidor no respondió a tiempo",
            "stage": "timeout"
        }
    except Exception as e:
        return {
            "success": False,
            "tenant_code": tenant.code,
            "endpoint": tenant.external_endpoint,
            "error": str(e),
            "stage": "unknown"
        }


@router.get(
    "/{tenant_id}/config",
    summary="Get tenant full configuration (including sensitive data)",
)
async def get_tenant_config(
    tenant_id: str,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Get full tenant configuration including external credentials.
    Only for admin panel editing purposes.
    """
    import json
    
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Parse external_headers
    extra_config = {}
    if tenant.external_headers:
        try:
            extra_config = json.loads(tenant.external_headers)
        except json.JSONDecodeError:
            pass
    
    return {
        "id": tenant.id,
        "code": tenant.code,
        "name": tenant.name,
        "contact_email": tenant.contact_email,
        "is_active": tenant.is_active,
        "integration_type": tenant.integration_type,
        # Inbound config
        "external_endpoint": tenant.external_endpoint,
        "external_token": tenant.external_token,  # Full token for editing
        "external_auth_type": tenant.external_auth_type,
        "hce_app": extra_config.get("app", ""),
        "hce_api_key": extra_config.get("api_key", ""),
        "hce_http_method": extra_config.get("http_method", "GET"),
        "hce_timeout_seconds": extra_config.get("timeout_seconds", 60),
        # Outbound config
        "allowed_scopes": tenant.allowed_scopes,
        "webhook_url": tenant.webhook_url,
        "webhook_secret": tenant.webhook_secret,
        # General
        "api_rate_limit": tenant.api_rate_limit,
        "notes": tenant.notes,
    }


@router.put(
    "/{tenant_id}/config",
    summary="Update tenant full configuration",
)
async def update_tenant_config(
    tenant_id: str,
    config: dict,
    user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Update full tenant configuration including external credentials.
    This is the main endpoint for configuring tenants from the admin panel.
    """
    import json
    
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    # Update basic fields
    if "name" in config:
        tenant.name = config["name"]
    if "contact_email" in config:
        tenant.contact_email = config["contact_email"]
    if "integration_type" in config:
        tenant.integration_type = config["integration_type"]
    
    # Update inbound config
    if "external_endpoint" in config:
        tenant.external_endpoint = config["external_endpoint"]
    if "external_token" in config:
        tenant.external_token = config["external_token"]
    if "external_auth_type" in config:
        tenant.external_auth_type = config["external_auth_type"]
    
    # Build external_headers JSON from HCE config
    extra_config = {}
    if tenant.external_headers:
        try:
            extra_config = json.loads(tenant.external_headers)
        except json.JSONDecodeError:
            pass
    
    if "hce_app" in config:
        extra_config["app"] = config["hce_app"]
    if "hce_api_key" in config:
        extra_config["api_key"] = config["hce_api_key"]
    if "hce_http_method" in config:
        extra_config["http_method"] = config["hce_http_method"]
    if "hce_timeout_seconds" in config:
        extra_config["timeout_seconds"] = config["hce_timeout_seconds"]
    
    tenant.external_headers = json.dumps(extra_config)
    
    # Update outbound config
    if "allowed_scopes" in config:
        tenant.allowed_scopes = config["allowed_scopes"]
    if "webhook_url" in config:
        tenant.webhook_url = config["webhook_url"]
    if "webhook_secret" in config:
        tenant.webhook_secret = config["webhook_secret"]
    
    # Update general
    if "api_rate_limit" in config:
        tenant.api_rate_limit = config["api_rate_limit"]
    if "notes" in config:
        tenant.notes = config["notes"]
    
    db.commit()
    db.refresh(tenant)
    
    log.info(f"Tenant config updated: {tenant.code} by user {user.get('username')}")
    
    return {"status": "updated", "tenant_id": tenant_id}
