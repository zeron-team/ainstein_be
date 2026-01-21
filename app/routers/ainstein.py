# app/routers/ainstein.py

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/ainstein", tags=["ainstein"])


@dataclass(frozen=True)
class AinsteinConfig:
    api_url: str
    app: str
    api_key: str
    token_header: str
    http_method: str
    timeout_seconds: float


def _get_cfg() -> AinsteinConfig:
    # ✅ Usar settings desde config.py que carga el .env correctamente
    from app.core.config import settings
    
    http_method = settings.AINSTEIN_HTTP_METHOD.strip().upper()
    # Permitimos GET/POST/PUT/etc por si el proveedor cambia
    if http_method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
        http_method = "GET"

    return AinsteinConfig(
        api_url=settings.AINSTEIN_API_URL,
        app=settings.AINSTEIN_APP,
        api_key=settings.AINSTEIN_API_KEY,
        token_header=settings.AINSTEIN_TOKEN,
        http_method=http_method,
        timeout_seconds=float(settings.AINSTEIN_TIMEOUT_SECONDS),
    )


def _require_env(cfg: AinsteinConfig) -> None:
    # En la colección Postman mandan apiKey en body y Token en header: necesitamos ambos
    if not cfg.api_key:
        raise HTTPException(
            status_code=500,
            detail="Falta configurar AINSTEIN_API_KEY en variables de entorno del backend.",
        )
    if not cfg.token_header:
        raise HTTPException(
            status_code=500,
            detail="Falta configurar AINSTEIN_TOKEN en variables de entorno del backend.",
        )


def _is_provider_error_json(payload: Any) -> bool:
    # Markey suele devolver {Estado:"ERROR", Mensaje:"..."} incluso con HTTP 200
    if not isinstance(payload, dict):
        return False
    estado = payload.get("Estado") or payload.get("estado")
    if isinstance(estado, str) and estado.strip().upper() == "ERROR":
        return True
    return False


async def _call_ainstein(payload: Dict[str, Any]) -> Any:
    """
    Llama a la API de AInstein/Markey.

    IMPORTANTE (según Postman provisto):
    - Método: GET
    - Header: Token: <...>
    - Body: JSON con {aplicacion, apiKey, operacion, filtro}

    Nota: GET con body no es estándar, pero httpx lo soporta con client.request(..., json=payload).
    """
    cfg = _get_cfg()
    _require_env(cfg)

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        # 🔑 Autenticación requerida por Postman
        "Token": cfg.token_header,
    }

    timeout = httpx.Timeout(cfg.timeout_seconds, connect=10.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            r = await client.request(
                cfg.http_method,
                cfg.api_url,
                json=payload,  # ✅ body JSON incluso con GET (tal como Postman)
                headers=headers,
            )
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Error de red llamando a AInstein: {str(e)}")

    # Si el servidor responde error HTTP
    if r.status_code >= 400:
        msg = r.text[:2000] if r.text else f"HTTP {r.status_code}"
        raise HTTPException(status_code=502, detail=f"AInstein respondió error HTTP: {msg}")

    # Parse JSON (o raw)
    try:
        data = r.json()
    except Exception:
        data = {"raw": r.text}

    # Si el proveedor devuelve Estado ERROR aunque sea 200
    if _is_provider_error_json(data):
        raise HTTPException(status_code=502, detail=f"AInstein respondió error: {data}")

    return data


@router.get("/episodios")
async def obtener_episodios(
    desde: str = Query(..., description="YYYY-MM-DD"),
    hasta: str = Query(..., description="YYYY-MM-DD"),
) -> Any:
    cfg = _get_cfg()
    payload = {
        "aplicacion": cfg.app,
        "apiKey": cfg.api_key,
        "operacion": "obtenerEpisodios",
        "filtro": {
            "inteFechaDesde": desde,
            "inteFechaHasta": hasta,
        },
    }
    return await _call_ainstein(payload)


@router.get("/historia")
async def obtener_historia_clinica(
    inteCodigo: int = Query(...),
    paciCodigo: int = Query(...),
) -> Any:
    cfg = _get_cfg()
    payload = {
        "aplicacion": cfg.app,
        "apiKey": cfg.api_key,
        "operacion": "obtenerHistoriaClinica",
        "filtro": {
            "inteCodigo": inteCodigo,
            "paciCodigo": paciCodigo,
        },
    }
    return await _call_ainstein(payload)