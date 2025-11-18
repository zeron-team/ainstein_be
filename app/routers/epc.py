# app/routers/epc.py
from __future__ import annotations

import json
import uuid
import logging
from datetime import datetime, date
from typing import Any, Dict, Optional, List
from uuid import UUID

from bson import ObjectId
from bson.binary import Binary, UUID_SUBTYPE
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.repositories.patient_repo import PatientRepo
from app.domain.models import User, Role, Admission, Patient
from app.adapters.mongo_client import (
    db as mongo,
    pick_hce_collections,
    list_existing_collections,
)
from app.core.config import settings
from app.services.ai_gemini_service import GeminiAIService

# from app.enums import PatientEstado, EPCEstado  # si querés usar los enums directamente

log = logging.getLogger(__name__)

router = APIRouter(prefix="/epc", tags=["EPC / Epicrisis"])


# -----------------------------------------------------------------------------
# Helpers generales
# -----------------------------------------------------------------------------
def _now() -> datetime:
    return datetime.utcnow()


def _uuid_str() -> str:
    return str(uuid.uuid4())


def _clean_str(s: Optional[str]) -> str:
    if not s:
        return ""
    return " ".join(str(s).split())


def _parse_dt_maybe(val: Any) -> Optional[datetime]:
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, date):
        return datetime(val.year, val.month, val.day)
    try:
        return datetime.fromisoformat(str(val))
    except Exception:
        pass
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(str(val), fmt)
        except Exception:
            continue
    return None


def _safe_objectid(value: Any) -> Optional[ObjectId]:
    if isinstance(value, ObjectId):
        return value
    try:
        return ObjectId(str(value))
    except Exception:
        return None


def _to_uuid_binary(s: str) -> Binary:
    """
    En Mongo a veces se guarda UUID como Binary subtype=4.
    """
    try:
        u = UUID(str(s))
        return Binary(u.bytes, UUID_SUBTYPE)
    except Exception:
        return Binary(b"\x00" * 16, UUID_SUBTYPE)


def _pick_best_hce_text(doc: Dict[str, Any]) -> str:
    """
    Priorizamos texto de HCE:
    1) text
    2) structured["texto_completo"] / ["texto"] / ["descripcion"]
    3) raw_text
    """
    if not doc:
        return ""
    if "text" in doc and isinstance(doc["text"], str) and doc["text"].strip():
        return doc["text"]
    structured = doc.get("structured") or {}
    if isinstance(structured, dict):
        for key in ("texto_completo", "texto", "descripcion"):
            val = structured.get(key)
            if isinstance(val, str) and val.strip():
                return val
    raw_text = doc.get("raw_text")
    if isinstance(raw_text, str) and raw_text.strip():
        return raw_text
    return ""


def _extract_hce_text(hce_doc: Dict[str, Any]) -> str:
    """
    Devuelve texto "usable" para generar la EPC.
    """
    base_text = _pick_best_hce_text(hce_doc)
    if base_text:
        return base_text

    parts: List[str] = []
    fields = [
        "motivo_internacion",
        "evolucion",
        "impresion_diagnostica",
        "diagnostico_principal",
        "diagnosticos_secundarios",
        "interconsultas",
        "procedimientos",
        "medicacion",
    ]
    structured = hce_doc.get("structured") or {}
    if isinstance(structured, dict):
        for f in fields:
            val = structured.get(f)
            if isinstance(val, str):
                parts.append(val)
            elif isinstance(val, list):
                parts.extend(str(v) for v in val if v)
    text = "\n\n".join(p for p in parts if p)
    return text


def _join_texts(docs: List[Dict[str, Any]]) -> str:
    texts: List[str] = []
    for d in docs:
        t = _extract_hce_text(d)
        if t:
            texts.append(t)
    return "\n\n".join(texts).strip()


def _json_from_ai(s: Any) -> Dict[str, Any]:
    """Normaliza la salida del modelo a un dict JSON.

    - Si ya viene un dict, lo devuelve tal cual.
    - Si viene vacío / None -> {}.
    - Si viene string, intenta:
        1) json.loads directo
        2) si falla, buscar el primer objeto {...} balanceando llaves.
    """
    # Caso 1: ya es dict
    if isinstance(s, dict):
        return s

    # Caso 2: vacío
    if not s:
        return {}

    # Normalizamos a string
    if not isinstance(s, str):
        try:
            s = json.dumps(s)
        except Exception:
            s = str(s)

    s = s.strip()
    try:
        return json.loads(s)
    except Exception:
        pass

    # Intento extraer el primer {...} balanceando llaves
    start = s.find("{")
    if start == -1:
        return {}
    depth = 0
    for i, ch in enumerate(s[start:], start=start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                frag = s[start : i + 1]
                try:
                    return json.loads(frag)
                except Exception:
                    return {}
    return {}


# -----------------------------------------------------------------------------
# Helper: sincronizar estado en SQL (paciente + admisión)
# -----------------------------------------------------------------------------
def _sync_estado_sql(
    db: Session,
    patient_id: Optional[str],
    admission_id: Optional[str],
    nuevo_estado: str,
    origin: str,
) -> None:
    """
    Sincroniza el campo `estado` en:
    - patients.estado
    - admissions.estado (primero intenta por id; si no, por patient_id)

    origin: texto para logging (ej. 'generate_epc' o 'update_epc')
    """
    if not patient_id:
        log.warning(
            "[%s] _sync_estado_sql llamado sin patient_id (admission_id=%s, estado=%s)",
            origin,
            admission_id,
            nuevo_estado,
        )
        return

    try:
        # ---------------- Paciente ----------------
        p_rows = (
            db.query(Patient)
            .filter(Patient.id == patient_id)
            .update({"estado": nuevo_estado}, synchronize_session=False)
        )

        # ---------------- Admisiones ----------------
        a_rows = 0

        # 1) Si tengo admission_id, intento actualizar esa sola
        if admission_id:
            a_rows = (
                db.query(Admission)
                .filter(Admission.id == admission_id)
                .update({"estado": nuevo_estado}, synchronize_session=False)
            )

        # 2) Si no tocó ninguna o no hay admission_id, actualizo por patient_id
        if a_rows == 0:
            a_rows = (
                db.query(Admission)
                .filter(Admission.patient_id == patient_id)
                .update({"estado": nuevo_estado}, synchronize_session=False)
            )

        db.commit()

        log.info(
            "[%s] Sync estado SQL OK | patient_id=%s p_rows=%s a_rows=%s nuevo_estado=%s",
            origin,
            patient_id,
            p_rows,
            a_rows,
            nuevo_estado,
        )
    except Exception as exc:
        db.rollback()
        log.warning(
            "[%s] Error sincronizando estado SQL "
            "(patient_id=%s, admission_id=%s, estado=%s): %s",
            origin,
            patient_id,
            admission_id,
            nuevo_estado,
            exc,
        )


# -----------------------------------------------------------------------------
# HCE: descubrimiento de colecciones
# -----------------------------------------------------------------------------
async def _discover_hce_collections(limit: Optional[int] = None):
    """
    Devuelve la lista de colecciones HCE combinando:
    - Candidatas estáticas (pick_hce_collections)
    - Descubrimiento dinámico: todas las colecciones cuyo nombre contenga 'hce' (case-insensitive)
      excluyendo 'epc_docs' y 'epc_versions'.

    El parámetro `limit` permite cortar la lista resultante para diagnóstico / logging,
    pero no afecta el descubrimiento en sí.
    """
    static_colls = await pick_hce_collections()
    static_names = {c.name for c in static_colls}

    try:
        existing = await list_existing_collections()
    except Exception:
        existing = []

    dyn_names: List[str] = []
    for name in existing or []:
        lname = name.lower()
        if "hce" in lname and name not in ("epc_docs", "epc_versions"):
            dyn_names.append(name)

    extra = [mongo[name] for name in dyn_names if name not in static_names]

    combined = static_colls + extra
    if limit is not None:
        return combined[:limit]
    return combined


async def _find_hce_by_id(hce_id: str) -> Optional[Dict[str, Any]]:
    colls = await _discover_hce_collections(limit=20)
    oid = _safe_objectid(hce_id)
    for c in colls:
        q = {"_id": oid} if oid else {"_id": hce_id}
        doc = await c.find_one(q)
        if doc:
            return doc
    return None


async def _find_latest_hce_for_patient(
    patient_id: str,
    admission_id: Optional[str] = None,
    dni: Optional[str] = None,
    allow_any: bool = True,
) -> Optional[Dict[str, Any]]:
    colls = await _discover_hce_collections(limit=20)

    # 1) por patient_id + admission_id
    if admission_id:
        for c in colls:
            doc = await c.find_one(
                {"patient_id": patient_id, "admission_id": admission_id},
                sort=[("created_at", -1)],
            )
            if doc:
                return doc

    # 2) solo patient_id
    for c in colls:
        doc = await c.find_one(
            {"patient_id": patient_id},
            sort=[("created_at", -1)],
        )
        if doc:
            return doc

    # 3) por dni
    if dni:
        for c in colls:
            doc = await c.find_one(
                {"dni": dni},
                sort=[("created_at", -1)],
            )
            if doc:
                return doc

    # 4) fallback ANY
    if allow_any:
        for c in colls:
            doc = await c.find_one(
                {"text": {"$exists": True}},
                sort=[("created_at", -1)],
            )
            if doc:
                return doc

    return None


# -----------------------------------------------------------------------------
# EPC: abrir/crear por paciente/admisión
# -----------------------------------------------------------------------------
class OpenEPCRequest(BaseModel):
    patient_id: str
    admission_id: Optional[str] = None


def _epc_out(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not doc:
        return {}
    return {
        "id": str(doc.get("_id")),
        "patient_id": doc.get("patient_id"),
        "admission_id": doc.get("admission_id"),
        "estado": doc.get("estado"),
        "titulo": doc.get("titulo"),
        "diagnostico_principal_cie10": doc.get("diagnostico_principal_cie10"),
        "fecha_emision": doc.get("fecha_emision"),
        "medico_responsable": doc.get("medico_responsable"),
        "firmado_por_medico": doc.get("firmado_por_medico", False),
        "created_by": doc.get("created_by"),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
        "generated": doc.get("generated"),
        "hce_origin_id": doc.get("hce_origin_id"),
    }


@router.post("/open")
async def open_epc_for_patient(
    body: OpenEPCRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Abre (o crea) una EPC en estado "borrador" para un paciente/admisión.

    El front envía JSON:
    {
      "patient_id": "...",
      "admission_id": null
    }
    """
    patient_id = body.patient_id
    admission_id = body.admission_id

    preg = PatientRepo(db).get(patient_id)
    if not preg:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")

    q: Dict[str, Any] = {"patient_id": patient_id}
    if admission_id:
        q["admission_id"] = admission_id

    existing = await mongo.epc_docs.find_one(q)
    if existing:
        return _epc_out(existing)

    _id = _uuid_str()
    doc = {
        "_id": _id,
        "patient_id": patient_id,
        "admission_id": admission_id,
        # EPC en Mongo sigue EPCEstado: empieza en borrador
        "estado": "borrador",
        "titulo": None,
        "diagnostico_principal_cie10": None,
        "fecha_emision": None,
        "medico_responsable": None,
        "firmado_por_medico": False,
        "created_by": str(user.id) if hasattr(user, "id") else None,
        "created_at": _now(),
        "updated_at": _now(),
        "generated": None,
        "hce_origin_id": None,
    }
    await mongo.epc_docs.insert_one(doc)
    return _epc_out(doc)


# -----------------------------------------------------------------------------
# Generar EPC desde IA (Gemini) usando HCE como fuente
# -----------------------------------------------------------------------------
@router.post(
    "/{epc_id}/generate",
    summary="Genera contenido de EPC usando IA y HCE",
)
async def generate_epc(
    epc_id: str,
    hce_id: Optional[str] = Query(
        default=None, description="Forzar la HCE a usar (_id de Mongo)"
    ),
    db: Session = Depends(get_db),
):
    epc_doc = await mongo.epc_docs.find_one({"_id": epc_id})
    if not epc_doc:
        raise HTTPException(status_code=404, detail="EPC no encontrado")

    patient_id = epc_doc.get("patient_id")
    if not patient_id:
        raise HTTPException(status_code=400, detail="EPC sin patient_id")

    admission_id = epc_doc.get("admission_id")

    # ------------------------------------------------------------------
    # 1) Resolver HCE origen
    # ------------------------------------------------------------------
    if hce_id:
        hce = await _find_hce_by_id(hce_id)
        if not hce:
            raise HTTPException(status_code=404, detail="HCE no encontrada (por hce_id)")
    else:
        dni = None
        preg = PatientRepo(db).get(patient_id)
        if preg and preg.dni:
            dni = preg.dni

        allow_any = settings.EPC_FALLBACK_ANY_HCE
        hce = await _find_latest_hce_for_patient(
            patient_id=patient_id,
            admission_id=admission_id,
            dni=dni,
            allow_any=allow_any,
        )

        if not hce:
            colls = await _discover_hce_collections(limit=12)
            names_counts: List[str] = []
            for c in colls[:12]:
                try:
                    text_cnt = await c.count_documents({"text": {"$exists": True}})
                except Exception:
                    text_cnt = -1
                try:
                    total_cnt = await c.estimated_document_count()
                except Exception:
                    total_cnt = -1
                names_counts.append(f"{c.name}(text:{text_cnt}, total:{total_cnt})")
            db_name = getattr(mongo, "name", "unknown_db")
            raise HTTPException(
                status_code=404,
                detail=(
                    "No hay HCE para generar contenido. Intenté: "
                    "[1] patient_id+admission_id, [2] solo patient_id, [3] por DNI"
                    + (" y [4] fallback ANY habilitado" if allow_any else "")
                    + f". DB='{db_name}'. Colecciones: {', '.join(names_counts)}"
                ),
            )

    # ------------------------------------------------------------------
    # 1.b) Sincronizar admission_id de la EPC con la HCE si estaba vacío
    # ------------------------------------------------------------------
    if hce and not admission_id:
        hce_adm = hce.get("admission_id")
        if hce_adm:
            admission_id = hce_adm
            epc_doc["admission_id"] = hce_adm
            try:
                await mongo.epc_docs.update_one(
                    {"_id": epc_id}, {"$set": {"admission_id": hce_adm}}
                )
            except Exception as exc:
                log.warning(
                    "No se pudo actualizar admission_id en EPC (epc_id=%s, hce_admission_id=%s): %s",
                    epc_id,
                    hce_adm,
                    exc,
                )

    # ------------------------------------------------------------------
    # 1.c) Corregir patient_id según HCE (para evitar desfasajes)
    # ------------------------------------------------------------------
    if hce:
        hce_patient_id = hce.get("patient_id")
        if hce_patient_id and hce_patient_id != patient_id:
            log.warning(
                "EPC %s tiene patient_id=%s pero HCE %s tiene patient_id=%s; "
                "se actualiza EPC para usar el de la HCE.",
                epc_id,
                patient_id,
                hce.get("_id"),
                hce_patient_id,
            )
            patient_id = hce_patient_id
            epc_doc["patient_id"] = patient_id
            try:
                await mongo.epc_docs.update_one(
                    {"_id": epc_id}, {"$set": {"patient_id": patient_id}}
                )
            except Exception as exc:
                log.warning(
                    "No se pudo actualizar patient_id en EPC (epc_id=%s, patient_id=%s): %s",
                    epc_id,
                    patient_id,
                    exc,
                )

    # ------------------------------------------------------------------
    # 2) Construir texto de entrada para IA
    # ------------------------------------------------------------------
    hce_text = _extract_hce_text(hce)
    if not hce_text:
        log.warning("HCE sin texto útil (id=%s)", hce.get("_id"))

    ai = GeminiAIService()
    prompt = f"""
Analiza el siguiente texto de una Historia Clínica Electrónica (HCE) y genera una EPICRISIS en formato JSON.

Reglas generales:
- SOLO devuelve el objeto JSON (sin comentarios, sin texto extra).
- Completa con "" o [] si algo no se deduce del texto (no inventes datos).
- Usa español (Argentina) y lenguaje médico formal.
- Usa TODA la información clínica relevante disponible en el texto. No resumas en exceso.

Requisitos específicos por campo:

- "motivo_internacion":
  - Debe ser una frase clara que explique por qué la paciente requirió internación
    (síntomas principales, mecanismo del trauma, motivo de consulta).
  - Ej.: "FRACTURA CERRADA DE DIÁFISIS DE CLAVÍCULA IZQUIERDA POR TRAUMATISMO EN VÍA PÚBLICA".

- "diagnostico_principal_cie10":
  - Código CIE-10 principal que mejor represente el motivo de internación, si puede inferirse.

- "evolucion":
  - DEBE ser un texto EXTENSO, mínimo 2 a 4 párrafos, con lenguaje médico.
  - Describir cronológicamente:
    - Antecedentes personales relevantes.
    - Motivo y forma de presentación (ej.: accidente de tránsito, caída, inicio de síntomas).
    - Evaluación inicial: signos y síntomas, hallazgos al examen físico.
    - Estudios complementarios realizados (ej.: Rx, TAC, laboratorio, ECO-FAST) y sus resultados.
    - Conducta diagnóstica y terapéutica durante la internación.
    - Evolución clínica hasta el alta, incluyendo respuesta al tratamiento y condición al egreso.
  - Evitar frases genéricas como "buena evolución" sin detalle.

- "procedimientos":
  - Lista de procedimientos diagnósticos o terapéuticos relevantes (ej.: inmovilización, yeso, cirugía, estudios de imágenes).

- "interconsultas":
  - Lista de interconsultas. Cada elemento puede ser:
    - Un string descriptivo, o
    - Un objeto con campos: "especialidad" y "resumen".

- "medicacion":
  - Lista de objetos con: "farmaco", "dosis", "via", "frecuencia".
  - Utilizar los datos de la HCE cuando estén disponibles.

- "indicaciones_alta" y "recomendaciones":
  - Listas de strings con indicaciones concretas (ej.: uso de cabestrillo, analgesia, control por consultorio externo, pautas de alarma).

Formato EXACTO de salida (solo este JSON, sin texto adicional):

{{
  "motivo_internacion": "",
  "diagnostico_principal_cie10": "",
  "evolucion": "",
  "procedimientos": [],
  "interconsultas": [],
  "medicacion": [{{"farmaco":"", "dosis":"", "via":"", "frecuencia":""}}],
  "indicaciones_alta": [],
  "recomendaciones": []
}}

\"\"\"{hce_text}\"\"\"
"""
    raw = await ai.generate_epc(prompt)

    # ------------------------------------------------------------------
    # 3) Parsear salida de IA (incluyendo raw_text interno)
    # ------------------------------------------------------------------
    data = _json_from_ai(raw) or {}
    if not isinstance(data, dict):
        data = {}

    if isinstance(data.get("raw_text"), str):
        inner = _json_from_ai(data["raw_text"])
        if isinstance(inner, dict):
            for k, v in inner.items():
                if k not in data:
                    data[k] = v

    # ------------------------------------------------------------------
    # 4) Normalizar campos generados
    # ------------------------------------------------------------------
    ts = _now().isoformat() + "Z"
    motivo = data.get("motivo_internacion", "") or ""
    diag_cie10 = data.get("diagnostico_principal_cie10", "") or ""
    evolucion = data.get("evolucion", "") or ""

    procedimientos = data.get("procedimientos", []) or []

    raw_interconsultas = data.get("interconsultas", []) or []
    interconsultas: List[str] = []
    interconsultas_detalle: List[Dict[str, Any]] = []
    for item in raw_interconsultas:
        if isinstance(item, dict):
            interconsultas_detalle.append(item)
            txt = item.get("resumen") or item.get("especialidad")
            if not txt:
                try:
                    txt = json.dumps(item, ensure_ascii=False)
                except Exception:
                    txt = str(item)
            interconsultas.append(_clean_str(txt))
        else:
            interconsultas.append(_clean_str(str(item)))

    try:
        data["interconsultas"] = interconsultas
        data["interconsultas_detalle"] = interconsultas_detalle
    except Exception:
        pass

    medicacion = data.get("medicacion", []) or []
    indicaciones_alta = data.get("indicaciones_alta", []) or []
    recomendaciones = data.get("recomendaciones", []) or []

    provider = "gemini"
    model = getattr(ai, "model", "gemini-2.0-flash")

    generated_doc = {
        "provider": provider,
        "model": model,
        "_provider": provider,
        "_model": model,
        "at": ts,
        "generated_at": ts,
        "hce_source_id": str(hce.get("_id")) if hce else None,
        "motivo_internacion": motivo,
        "diagnostico_principal_cie10": diag_cie10,
        "evolucion": evolucion,
        "procedimientos": procedimientos,
        "interconsultas": interconsultas,
        "interconsultas_detalle": interconsultas_detalle,
        "medicacion": medicacion,
        "indicaciones_alta": indicaciones_alta,
        "recomendaciones": recomendaciones,
        "data": data,
    }

    # ------------------------------------------------------------------
    # 5) Persistir en Mongo y sincronizar estados SQL
    # ------------------------------------------------------------------
    await mongo.epc_docs.update_one(
        {"_id": epc_id},
        {
            "$set": {
                "generated": generated_doc,
                "hce_origin_id": generated_doc["hce_source_id"],
                "updated_at": _now(),
            }
        },
    )

    # Usamos PatientEstado.epc_generada -> "epc_generada"
    _sync_estado_sql(
        db=db,
        patient_id=patient_id,
        admission_id=admission_id,
        nuevo_estado="epc_generada",
        origin="generate_epc",
    )

    version_doc = {
        "_id": _uuid_str(),
        "epc_id": epc_id,
        "patient_id": patient_id,
        "created_at": _now(),
        "source": "ai_generate",
        "generated": generated_doc,
    }
    await mongo.epc_versions.insert_one(version_doc)

    return {
        "epc_id": epc_id,
        "version_id": version_doc["_id"],
        "status": "ok",
    }


# -----------------------------------------------------------------------------
# Obtener EPC y versiones
# -----------------------------------------------------------------------------
@router.get("/{epc_id}")
async def get_epc(epc_id: str):
    doc = await mongo.epc_docs.find_one({"_id": epc_id})
    if not doc:
        raise HTTPException(status_code=404, detail="EPC no encontrado")
    return _epc_out(doc)


@router.get("/{epc_id}/versions")
async def list_epc_versions(epc_id: str):
    cursor = mongo.epc_versions.find({"epc_id": epc_id}).sort("created_at", -1)
    items: List[Dict[str, Any]] = []
    async for d in cursor:
        items.append(
            {
                "id": str(d.get("_id")),
                "created_at": d.get("created_at"),
                "source": d.get("source"),
                "provider": d.get("generated", {}).get("provider"),
                "model": d.get("generated", {}).get("model"),
            }
        )
    return {
        "items": items,
        "total": len(items),
    }


@router.get("/{epc_id}/versions/{version_id}")
async def get_epc_version(epc_id: str, version_id: str):
    doc = await mongo.epc_versions.find_one({"_id": version_id, "epc_id": epc_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Versión no encontrada")
    gen = doc.get("generated") or {}
    return {
        "id": str(doc.get("_id")),
        "epc_id": epc_id,
        "created_at": doc.get("created_at"),
        "source": doc.get("source"),
        "generated": gen,
    }


# -----------------------------------------------------------------------------
# Contexto de EPC: paciente + HCE asociada
# -----------------------------------------------------------------------------
@router.get("/{epc_id}/context")
async def get_epc_context(
    epc_id: str,
    db: Session = Depends(get_db),
):
    """
    Devuelve el contexto para la vista de EPC:
    - Datos básicos de la EPC
    - Datos básicos del paciente
    - Última HCE asociada (o la de origen)
    - Contenido generado
    - Datos clínicos derivados de la HCE (admision, protocolo, fechas, sector, hab, cama)
    """
    epc_doc = await mongo.epc_docs.find_one({"_id": epc_id})
    if not epc_doc:
        raise HTTPException(status_code=404, detail="EPC no encontrado")

    patient_id = epc_doc.get("patient_id")
    patient = None
    if patient_id:
        patient = PatientRepo(db).get(patient_id)

    hce: Optional[Dict[str, Any]] = None
    hce_origin_id = epc_doc.get("hce_origin_id")
    if hce_origin_id:
        hce = await _find_hce_by_id(str(hce_origin_id))

    if not hce and patient_id:
        dni = getattr(patient, "dni", None) if patient else None
        hce = await _find_latest_hce_for_patient(
            patient_id=patient_id,
            admission_id=epc_doc.get("admission_id"),
            dni=dni,
            allow_any=settings.EPC_FALLBACK_ANY_HCE,
        )

    hce_text = _extract_hce_text(hce) if hce else ""

    patient_out: Optional[Dict[str, Any]] = None
    if patient:
        patient_out = {
            "id": patient.id,
            "apellido": getattr(patient, "apellido", None),
            "nombre": getattr(patient, "nombre", None),
            "dni": getattr(patient, "dni", None),
            "obra_social": getattr(patient, "obra_social", None),
            "nro_beneficiario": getattr(patient, "nro_beneficiario", None),
        }

    structured = (hce or {}).get("structured") or {}

    clinical = {
        "admision_num": (
            structured.get("admision_num")
            or structured.get("admission_num")
            or structured.get("numero_admision")
            or structured.get("nro_admision")
            or structured.get("Nro Admisión")
            or structured.get("Nro Admision")
        ),
        "protocolo": (
            structured.get("protocolo")
            or structured.get("protocolo_num")
            or structured.get("numero_protocolo")
            or structured.get("Nro Protocolo")
        ),
        "fecha_ingreso": (
            structured.get("fecha_ingreso")
            or structured.get("fecha_admision")
            or structured.get("ingreso_fecha")
            or structured.get("Fecha Ingreso")
            or structured.get("Fecha de Ingreso")
        ),
        "fecha_egreso": (
            structured.get("fecha_egreso")
            or structured.get("fecha_alta")
            or structured.get("egreso_fecha")
            or structured.get("Fecha Egreso")
            or structured.get("Fecha de Egreso")
        ),
        "sector": (
            structured.get("sector")
            or structured.get("servicio")
            or structured.get("unidad")
            or structured.get("sector_internacion")
            or structured.get("Sector")
            or structured.get("Servicio")
        ),
        "habitacion": (
            structured.get("habitacion")
            or structured.get("hab")
            or structured.get("habitacion_num")
            or structured.get("nro_habitacion")
            or structured.get("Habitacion")
            or structured.get("Hab.")
        ),
        "cama": (
            structured.get("cama")
            or structured.get("cama_num")
            or structured.get("nro_cama")
            or structured.get("Cama")
        ),
        "numero_historia_clinica": (
            structured.get("numero_historia_clinica")
            or structured.get("nro_hc")
            or structured.get("hc_numero")
            or structured.get("historia_clinica")
            or structured.get("Historia Clínica")
            or structured.get("Nro Historia Clínica")
        ),
    }

    for key in ("fecha_ingreso", "fecha_egreso"):
        val = clinical.get(key)
        dt = _parse_dt_maybe(val)
        if dt:
            clinical[key + "_display"] = dt.strftime("%d/%m/%Y")

    hce_out: Optional[Dict[str, Any]] = None
    if hce:
        hce_out = {
            "id": str(hce.get("_id")),
            "patient_id": hce.get("patient_id"),
            "admission_id": hce.get("admission_id"),
            "created_at": hce.get("created_at"),
            "structured": structured,
            "clinical": clinical,
        }

    epc_out = _epc_out(epc_doc)
    for k, v in clinical.items():
        if v is not None and k not in epc_out:
            epc_out[k] = v

    generated = epc_doc.get("generated") or {}

    return {
        "epc": epc_out,
        "generated": generated,
        "patient": patient_out,
        "hce": hce_out,
        "hce_text": hce_text,
        "clinical": clinical,
    }


# -----------------------------------------------------------------------------
# Actualizar campos manuales EPC
# -----------------------------------------------------------------------------
@router.patch("/{epc_id}")
async def update_epc(
    epc_id: str,
    payload: Dict[str, Any],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = await mongo.epc_docs.find_one({"_id": epc_id})
    if not doc:
        raise HTTPException(status_code=404, detail="EPC no encontrado")

    updates: Dict[str, Any] = {}
    allowed_fields = [
        "titulo",
        "diagnostico_principal_cie10",
        "fecha_emision",
        "medico_responsable",
        "firmado_por_medico",
        "estado",
    ]
    for f in allowed_fields:
        if f in payload:
            updates[f] = payload[f]

    if "estado" in updates and doc.get("patient_id"):
        patient_id = doc.get("patient_id")
        admission_id = doc.get("admission_id")
        nuevo_estado_epc = updates["estado"]

        if nuevo_estado_epc in ("validada", "impresa"):
            nuevo_estado_paciente = "epc_generada"
        else:
            nuevo_estado_paciente = "internacion"

        _sync_estado_sql(
            db=db,
            patient_id=patient_id,
            admission_id=admission_id,
            nuevo_estado=nuevo_estado_paciente,
            origin="update_epc",
        )

    if not updates:
        return _epc_out(doc)

    updates["updated_at"] = _now()
    await mongo.epc_docs.update_one({"_id": epc_id}, {"$set": updates})

    new_doc = await mongo.epc_docs.find_one({"_id": epc_id})
    return _epc_out(new_doc or doc)