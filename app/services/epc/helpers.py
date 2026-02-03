# app/services/epc/helpers.py
"""
Funciones auxiliares para EPC.

Extraídas de routers/epc.py para cumplir con Single Responsibility.
"""

from __future__ import annotations

import json
import uuid
import re
import logging
from datetime import datetime, date
from typing import Any, Dict, Optional, List
from bson import ObjectId, Binary
from uuid import UUID

log = logging.getLogger(__name__)


def now() -> datetime:
    """Retorna datetime actual UTC."""
    return datetime.utcnow()


def uuid_str() -> str:
    """Genera un nuevo UUID como string."""
    return str(uuid.uuid4())


def clean_str(s: Optional[str]) -> str:
    """Limpia un string, colapsa espacios múltiples, o retorna vacío."""
    if not s:
        return ""
    return " ".join(str(s).split())


def parse_dt_maybe(val: Any) -> Optional[datetime]:
    """
    Intenta parsear un valor como datetime.
    Soporta múltiples formatos.
    """
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, date):
        return datetime.combine(val, datetime.min.time())
    if isinstance(val, str):
        val = val.strip()
        for fmt in (
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y",
        ):
            try:
                return datetime.strptime(val, fmt)
            except ValueError:
                pass
    return None


def safe_objectid(value: Any) -> Optional[ObjectId]:
    """Convierte a ObjectId si es válido."""
    if isinstance(value, ObjectId):
        return value
    if isinstance(value, str) and ObjectId.is_valid(value):
        return ObjectId(value)
    return None


def uuid_variants(val: Optional[str]) -> List[Any]:
    """
    Devuelve variantes para matchear UUID guardado como:
    - string
    - Binary(UUID_SUBTYPE=4)
    """
    if not val:
        return []
    variants = [val]
    try:
        from bson import Binary
        u = UUID(val)
        variants.append(Binary(u.bytes, subtype=4))
    except Exception:
        pass
    return variants


def to_uuid_binary(s: str) -> Optional[Binary]:
    """En Mongo a veces se guarda UUID como Binary subtype=4."""
    try:
        from bson import Binary
        u = UUID(s)
        return Binary(u.bytes, subtype=4)
    except Exception:
        return None


def json_from_ai(s: Any) -> Dict[str, Any]:
    """
    Normaliza la salida del modelo a un dict JSON.
    
    - Si ya viene un dict, lo devuelve tal cual.
    - Si viene vacío / None -> {}.
    - Si viene string, intenta:
        1) json.loads directo
        2) si falla, buscar el primer objeto {...} balanceando llaves.
    """
    if s is None:
        return {}
    if isinstance(s, dict):
        return s
    if not isinstance(s, str):
        return {}
    
    s = s.strip()
    if not s:
        return {}
    
    # Intento 1: JSON directo
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    
    # Intento 2: Buscar objeto JSON balanceado
    start = s.find("{")
    if start == -1:
        return {}
    
    depth = 0
    end = start
    for i, c in enumerate(s[start:], start):
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    
    try:
        return json.loads(s[start:end])
    except json.JSONDecodeError:
        return {}


def actor_name(user: Any) -> str:
    """
    Obtiene un nombre legible del usuario para el historial.
    
    Intenta, en este orden:
    - full_name
    - username
    - email
    """
    if not user:
        return "sistema"
    
    # Soporta dict y objetos
    if isinstance(user, dict):
        return (
            user.get("full_name") or
            user.get("username") or
            user.get("email") or
            "usuario"
        )
    
    return (
        getattr(user, "full_name", None) or
        getattr(user, "username", None) or
        getattr(user, "email", None) or
        "usuario"
    )


def age_from_ymd(ymd: Optional[str]) -> Optional[int]:
    """Calcula edad desde fecha YYYY-MM-DD."""
    if not ymd:
        return None
    try:
        born = datetime.strptime(ymd[:10], "%Y-%m-%d")
        today = date.today()
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    except Exception:
        return None


def list_to_lines(items: Any) -> str:
    """
    Convierte listas de strings/objetos a texto multilínea para PDF.
    - strings: "• item"
    - dict medicación: "• farmaco · dosis · via · frecuencia"
    - otros dict: intenta descripcion/detalle/resumen/especialidad o JSON
    """
    if not items:
        return ""
    if isinstance(items, str):
        return items
    if not isinstance(items, list):
        return str(items)
    
    lines = []
    for item in items:
        if isinstance(item, str):
            lines.append(f"• {item}")
        elif isinstance(item, dict):
            # Medicación
            if "farmaco" in item:
                parts = [
                    item.get("farmaco", ""),
                    item.get("dosis", ""),
                    item.get("via", ""),
                    item.get("frecuencia", ""),
                ]
                lines.append("• " + " · ".join(p for p in parts if p))
            # Otros objetos
            else:
                text = (
                    item.get("descripcion") or
                    item.get("detalle") or
                    item.get("resumen") or
                    item.get("especialidad") or
                    json.dumps(item, ensure_ascii=False)
                )
                lines.append(f"• {text}")
        else:
            lines.append(f"• {item}")
    
    return "\n".join(lines)
