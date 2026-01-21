# backend/app/utils/normalize_ws_payload.py

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _safe_json_loads(s: str):
    try:
        return json.loads(s)
    except Exception:
        return s


def _to_iso(dt_str: Optional[str]) -> Optional[str]:
    """Convierte strings de fecha variados a ISO UTC (si puede). Si no, devuelve original."""
    if not dt_str or not isinstance(dt_str, str):
        return None

    s = dt_str.strip()

    # Caso DD/MM/YYYY HH:MM (muy común en plantillas)
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})\s+(\d{2}):(\d{2})(?::(\d{2}))?$", s)
    if m:
        dd, mm, yyyy, HH, MM, SS = m.group(1, 2, 3, 4, 5, 6)
        SS = SS or "00"
        dt = datetime(
            int(yyyy),
            int(mm),
            int(dd),
            int(HH),
            int(MM),
            int(SS),
            tzinfo=timezone.utc,
        )
        return dt.isoformat().replace("+00:00", "Z")

    # Caso ISO sin tz: 2025-12-19T17:46:36 / con fracciones
    try:
        # Python acepta fracción 1..6 dígitos; si trae "Z" lo manejamos
        if s.endswith("Z"):
            s2 = s[:-1]
            dt = datetime.fromisoformat(s2)
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except Exception:
        return dt_str  # no rompemos


def normalize_ws_payload(doc: Dict[str, Any], max_historia: int = 40) -> Dict[str, Any]:
    """
    Normaliza el payload 'doc' para que sea consistente, estable y no rompa:
    - Limpia _id (si viene de export Mongo).
    - Convierte doc["text"] si es JSON string.
    - Garantiza dicts en structured/source/ainstein.
    - Normaliza fechas a ISO UTC (Z) donde aplique.
    - Evita None en strings claves (para concatenación).
    - Normaliza episodio/historia: fechas, listas nulas -> [], recorte por tamaño.
    - pages=0 => pages=1 para no usarlo como validador.
    """
    doc = dict(doc)  # copia

    # 1) limpiar _id si viene estilo Mongo export
    doc.pop("_id", None)

    # 2) text: si es string JSON -> dict
    if isinstance(doc.get("text"), str):
        doc["text"] = _safe_json_loads(doc["text"])

    # 3) defaults básicos (asegurar dicts)
    doc["pages"] = int(doc.get("pages") or 0)

    if not isinstance(doc.get("structured"), dict):
        doc["structured"] = {}
    if not isinstance(doc.get("source"), dict):
        doc["source"] = {}
    if not isinstance(doc.get("ainstein"), dict):
        doc["ainstein"] = {}

    st = doc["structured"]
    st.setdefault("paciente_apellido_nombre", "")
    st.setdefault("sexo", None)

    # 4) fechas principales a ISO
    st["fecha_ingreso"] = _to_iso(st.get("fecha_ingreso"))
    st["fecha_egreso_original"] = _to_iso(st.get("fecha_egreso_original"))

    # 5) normalizar nulls de strings a "" donde suele fallar la concatenación
    for k in [
        "sector",
        "habitacion",
        "cama",
        "protocolo",
        "admision_num",
        "estado_internacion",
    ]:
        if st.get(k) is None:
            st[k] = ""

    # 6) normalizar episodio
    ep = (doc.get("ainstein") or {}).get("episodio") or {}
    if isinstance(ep, dict) and ep:
        ep["inteFechaIngreso"] = _to_iso(ep.get("inteFechaIngreso"))
        ep["inteFechaEgreso"] = _to_iso(ep.get("inteFechaEgreso"))
        for mov in ep.get("movimientos") or []:
            if isinstance(mov, dict):
                mov["inmoFechaDesde"] = _to_iso(mov.get("inmoFechaDesde"))
        doc["ainstein"]["episodio"] = ep

    # 7) historia: asegurar listas, fechas y recorte (para no romper por tamaño)
    historia: List[Dict[str, Any]] = (doc.get("ainstein") or {}).get("historia") or []
    if not isinstance(historia, list):
        historia = []

    cleaned: List[Dict[str, Any]] = []
    for h in historia:
        if not isinstance(h, dict):
            continue

        h = dict(h)
        h["entrFechaAtencion"] = _to_iso(h.get("entrFechaAtencion"))

        # listas nulas -> []
        for lk in [
            "diagnosticos",
            "plantillas",
            "indicacionFarmacologica",
            "indicacionProcedimientos",
            "indicacionEnfermeria",
        ]:
            if h.get(lk) is None:
                h[lk] = []
            elif not isinstance(h.get(lk), list):
                h[lk] = []

        # plantillas.propiedades nulo -> []
        for pl in h.get("plantillas", []):
            if isinstance(pl, dict) and pl.get("propiedades") is None:
                pl["propiedades"] = []
            elif isinstance(pl, dict) and not isinstance(pl.get("propiedades"), list):
                pl["propiedades"] = []

        cleaned.append(h)

    # recorte: quedate con lo más relevante y reciente
    # (prioriza Evolución médica y diagnósticos)
    priority_types = {
        "EVOLUCION MEDICA (A CARGO)",
        "INGRESO A PISO",
        "INGRESO DE PACIENTE",
        "EVOLUCION EMERGENCIA",
        "HOJA DE ENFERMERIA",
    }
    prioritized = [x for x in cleaned if (x.get("entrTipoRegistro") in priority_types)]
    tail = cleaned[-max_historia:] if len(cleaned) > max_historia else cleaned

    # asegurar ainstein dict
    if not isinstance(doc.get("ainstein"), dict):
        doc["ainstein"] = {}
    doc["ainstein"]["historia"] = (prioritized + tail)[-max_historia:]

    # 8) si pages=0, no lo uses como validador (o poné 1)
    if doc["pages"] == 0:
        doc["pages"] = 1

    return doc