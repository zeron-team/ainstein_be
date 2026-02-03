# app/routers/ainstein.py
"""
Multi-tenant Ainstein/HCE integration router.
All configuration comes from the tenant database, NOT from .env files.
This enables true multi-tenancy where each tenant has its own credentials.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.domain.models import Tenant

router = APIRouter(prefix="/ainstein", tags=["ainstein"])


@dataclass(frozen=True)
class TenantHCEConfig:
    """Configuration for connecting to a tenant's HCE system."""
    tenant_id: str
    tenant_code: str
    api_url: str
    app: str
    api_key: str
    token_header: str
    http_method: str
    timeout_seconds: float


def get_tenant_config(tenant_code: str, db: Session) -> TenantHCEConfig:
    """
    Get HCE connection config from the tenant database.
    This is the core of multi-tenancy - each tenant has its own credentials.
    """
    tenant = db.query(Tenant).filter(
        Tenant.code == tenant_code,
        Tenant.is_active == True
    ).first()
    
    if not tenant:
        raise HTTPException(
            status_code=404,
            detail=f"Tenant '{tenant_code}' no encontrado o inactivo"
        )
    
    # For inbound integrations, we need external credentials
    if tenant.integration_type not in ("inbound", "bidirectional"):
        raise HTTPException(
            status_code=400,
            detail=f"Tenant '{tenant_code}' no tiene configuración de integración entrante (HCE)"
        )
    
    if not tenant.external_endpoint:
        raise HTTPException(
            status_code=400,
            detail=f"Tenant '{tenant_code}' no tiene endpoint externo configurado"
        )
    
    if not tenant.external_token:
        raise HTTPException(
            status_code=400,
            detail=f"Tenant '{tenant_code}' no tiene token externo configurado"
        )
    
    # Parse additional config from external_headers (JSON)
    extra_config = {}
    if tenant.external_headers:
        try:
            extra_config = json.loads(tenant.external_headers)
        except json.JSONDecodeError:
            pass
    
    http_method = extra_config.get("http_method", "GET").upper()
    if http_method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
        http_method = "GET"
    
    return TenantHCEConfig(
        tenant_id=tenant.id,
        tenant_code=tenant.code,
        api_url=tenant.external_endpoint,
        app=extra_config.get("app", "AInstein"),
        api_key=extra_config.get("api_key", ""),
        token_header=tenant.external_token,
        http_method=http_method,
        timeout_seconds=float(extra_config.get("timeout_seconds", 60)),
    )


def _is_provider_error_json(payload: Any) -> bool:
    """Check if the provider returned an error in JSON format."""
    if not isinstance(payload, dict):
        return False
    estado = payload.get("Estado") or payload.get("estado")
    if isinstance(estado, str) and estado.strip().upper() == "ERROR":
        return True
    return False


async def _call_tenant_hce(cfg: TenantHCEConfig, payload: Dict[str, Any]) -> Any:
    """
    Call a tenant's HCE API with their specific credentials.
    
    IMPORTANT: This supports various HCE implementations:
    - GET with JSON body (Markey style)
    - POST with JSON body (standard REST)
    """
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Token": cfg.token_header,  # Authentication header
    }

    timeout = httpx.Timeout(cfg.timeout_seconds, connect=10.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            r = await client.request(
                cfg.http_method,
                cfg.api_url,
                json=payload,
                headers=headers,
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=502, 
                detail=f"Error de red conectando al HCE de {cfg.tenant_code}: {str(e)}"
            )

    if r.status_code >= 400:
        msg = r.text[:2000] if r.text else f"HTTP {r.status_code}"
        raise HTTPException(
            status_code=502, 
            detail=f"HCE de {cfg.tenant_code} respondió error HTTP: {msg}"
        )

    try:
        data = r.json()
    except Exception:
        data = {"raw": r.text}

    if _is_provider_error_json(data):
        raise HTTPException(
            status_code=502, 
            detail=f"HCE de {cfg.tenant_code} respondió error: {data}"
        )

    return data


# =============================================================================
# PUBLIC ENDPOINTS - Now tenant-aware
# =============================================================================

@router.get("/episodios")
async def obtener_episodios(
    tenant: str = Query(..., description="Código del tenant (ej: 'markey')"),
    desde: str = Query(..., description="YYYY-MM-DD"),
    hasta: str = Query(..., description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
) -> Any:
    """
    Obtener episodios de un tenant específico.
    La configuración se obtiene de la base de datos, no del .env.
    """
    cfg = get_tenant_config(tenant, db)
    
    payload = {
        "aplicacion": cfg.app,
        "apiKey": cfg.api_key,
        "operacion": "obtenerEpisodios",
        "filtro": {
            "inteFechaDesde": desde,
            "inteFechaHasta": hasta,
        },
    }
    return await _call_tenant_hce(cfg, payload)


@router.get("/historia")
async def obtener_historia_clinica(
    tenant: str = Query(..., description="Código del tenant (ej: 'markey')"),
    inteCodigo: int = Query(...),
    paciCodigo: int = Query(...),
    db: Session = Depends(get_db),
) -> Any:
    """
    Obtener historia clínica de un tenant específico.
    """
    cfg = get_tenant_config(tenant, db)
    
    payload = {
        "aplicacion": cfg.app,
        "apiKey": cfg.api_key,
        "operacion": "obtenerHistoriaClinica",
        "filtro": {
            "inteCodigo": inteCodigo,
            "paciCodigo": paciCodigo,
        },
    }
    return await _call_tenant_hce(cfg, payload)


@router.get("/test-connection")
async def test_tenant_connection(
    tenant: str = Query(..., description="Código del tenant a probar"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Test the connection to a tenant's HCE system.
    Useful for validating configuration from the admin panel.
    """
    try:
        cfg = get_tenant_config(tenant, db)
    except HTTPException as e:
        return {
            "success": False,
            "tenant": tenant,
            "error": e.detail,
            "stage": "config"
        }
    
    # Try a basic request
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Token": cfg.token_header,
    }
    
    timeout = httpx.Timeout(10.0, connect=5.0)
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Send a minimal request to check connectivity
            r = await client.request(
                cfg.http_method,
                cfg.api_url,
                json={
                    "aplicacion": cfg.app,
                    "apiKey": cfg.api_key,
                    "operacion": "ping",  # Probably will fail but shows connectivity
                    "filtro": {},
                },
                headers=headers,
            )
            
            return {
                "success": True,
                "tenant": tenant,
                "endpoint": cfg.api_url,
                "http_status": r.status_code,
                "response_preview": r.text[:200] if r.text else None,
            }
            
    except httpx.RequestError as e:
        return {
            "success": False,
            "tenant": tenant,
            "endpoint": cfg.api_url,
            "error": str(e),
            "stage": "connection"
        }