# backend/app/api/routes/ingest.py

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException, Query

from app.services.ingest_service import ingest_document

router = APIRouter(prefix="/api", tags=["ingest"])


@router.post("/ingest")
async def ingest_endpoint(
    payload: Dict[str, Any] = Body(...),
    max_historia: int = Query(40, ge=1, le=200),
    return_normalized: bool = Query(False),
):
    """
    Recibe un JSON (payload), lo normaliza y devuelve metadata.
    - max_historia: recorta historia para evitar payload enorme.
    - return_normalized: si true, devuelve el doc normalizado completo.
    """
    try:
        return ingest_document(
            payload,
            max_historia=max_historia,
            return_normalized=return_normalized,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno en ingest: {e}")