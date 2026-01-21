# backend/app/services/ingest_service.py

import json
import logging
from typing import Any, Dict, Optional
from uuid import uuid4

from app.utils.normalize_ws_payload import normalize_ws_payload

logger = logging.getLogger(__name__)


def _build_doc_id(normalized: Dict[str, Any]) -> str:
    """
    Intenta construir un ID estable desde campos clínicos; si no puede, genera UUID.
    """
    st = normalized.get("structured") or {}
    if not isinstance(st, dict):
        st = {}

    adm = (st.get("admision_num") or "").strip()
    prot = (st.get("protocolo") or "").strip()

    if adm and prot:
        return f"adm:{adm}|prot:{prot}"

    if adm:
        return f"adm:{adm}"

    return f"uuid:{uuid4()}"


def _to_text_for_index(normalized: Dict[str, Any]) -> str:
    """
    Genera un texto razonable (y estable) para embeddings/indexación.
    """
    text = normalized.get("text")

    # Si text es dict/list -> json pretty compacto
    if isinstance(text, (dict, list)):
        try:
            return json.dumps(text, ensure_ascii=False, separators=(",", ":"))
        except Exception:
            return str(text)

    if isinstance(text, str):
        return text.strip()

    # fallback: usar partes del structured
    st = normalized.get("structured") or {}
    if isinstance(st, dict):
        parts = []
        for k in [
            "paciente_apellido_nombre",
            "sector",
            "habitacion",
            "cama",
            "estado_internacion",
            "fecha_ingreso",
            "fecha_egreso_original",
        ]:
            v = st.get(k)
            if v:
                parts.append(f"{k}: {v}")
        if parts:
            return "\n".join(parts)

    return ""


def ingest_document(
    payload: Dict[str, Any],
    *,
    max_historia: int = 40,
    return_normalized: bool = False,
) -> Dict[str, Any]:
    """
    Punto único de entrada para:
    1) Normalizar payload.
    2) Generar doc_id.
    3) Preparar texto para indexación/embeddings.
    4) (Opcional) En tu implementación real: guardar en DB / upsert Qdrant.

    Devuelve un dict con metadata + (opcional) el doc normalizado.
    """
    if not isinstance(payload, dict):
        raise ValueError("payload debe ser un objeto JSON (dict).")

    normalized = normalize_ws_payload(payload, max_historia=max_historia)
    doc_id = _build_doc_id(normalized)
    text_for_index = _to_text_for_index(normalized)

    # Aquí integrarías:
    # - persistencia DB (Mongo/Postgres)
    # - embeddings
    # - upsert Qdrant
    #
    # Ej:
    # db.save(doc_id, normalized)
    # vectors = embed(text_for_index)
    # qdrant.upsert(collection, doc_id, vectors, payload=normalized)

    result: Dict[str, Any] = {
        "ok": True,
        "doc_id": doc_id,
        "pages": normalized.get("pages", 0),
        "text_len": len(text_for_index or ""),
    }

    if return_normalized:
        result["normalized"] = normalized

    logger.info("Ingest OK doc_id=%s pages=%s text_len=%s", doc_id, result["pages"], result["text_len"])
    return result