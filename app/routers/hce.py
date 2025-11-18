from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from bson import ObjectId
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.adapters.mongo_client import db as mongo
from app.services.hce_parser import (
    save_upload,
    extract_text_from_hce,
    parse_hce_text,
)

try:
    from app.domain.models import Patient, Admission  # type: ignore
except Exception:  # pragma: no cover
    Patient = None  # type: ignore
    Admission = None  # type: ignore

try:
    from app.services.ai_gemini_service import GeminiAIService  # type: ignore
except Exception:  # pragma: no cover
    GeminiAIService = None  # type: ignore

router = APIRouter(prefix="/hce", tags=["HCE"])


# ----------------- helpers -----------------
def _split_ap_nom(apynom: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    if not apynom:
        return None, None
    parts = [p.strip() for p in apynom.split(",")]
    apellido = parts[0] if parts else None
    nombre = parts[1] if len(parts) > 1 else None
    return apellido or None, nombre or None

def _to_oid(maybe_id: str):
    return ObjectId(maybe_id) if ObjectId.is_valid(maybe_id) else maybe_id

def _ensure_patient_and_admission(
    db: Session,
    *,
    patient_id: Optional[str],
    structured: Dict[str, Any],
) -> Tuple[str, Optional[str]]:
    if Patient is None:
        raise HTTPException(500, detail="Modelos de dominio no disponibles (Patient/Admission).")

    apellido, nombre = _split_ap_nom(structured.get("paciente_apellido_nombre"))
    sexo = structured.get("sexo")

    # 1) Patient
    pid = patient_id
    if not pid:
        q = db.query(Patient)
        if apellido:
            q = q.filter(Patient.apellido == apellido)
        if nombre:
            q = q.filter(Patient.nombre == nombre)
        found = q.first()
        if found:
            pid = found.id
        else:
            pid = str(uuid.uuid4())
            db.add(
                Patient(
                    id=pid,
                    apellido=apellido or "PACIENTE",
                    nombre=nombre or "SIN NOMBRE",
                    sexo=sexo,
                    obra_social=structured.get("obra_social"),
                    nro_beneficiario=structured.get("nro_beneficiario"),
                )
            )
            db.commit()

    # 2) Admission
    adm_id: Optional[str] = None
    if Admission is not None:
        tiene_algo = any(
            [
                structured.get("fecha_ingreso"),
                structured.get("fecha_egreso"),
                structured.get("admision_num"),
                structured.get("protocolo"),
                structured.get("sector"),
                structured.get("habitacion"),
                structured.get("cama"),
            ]
        )
        if tiene_algo:
            adm_id = str(uuid.uuid4())
            try:
                fi = structured.get("fecha_ingreso")
                fe = structured.get("fecha_egreso")
                db.add(
                    Admission(
                        id=adm_id,
                        patient_id=pid,
                        sector=structured.get("sector"),
                        habitacion=structured.get("habitacion"),
                        cama=structured.get("cama"),
                        fecha_ingreso=(datetime.fromisoformat(fi) if fi else datetime.utcnow()),
                        fecha_egreso=(datetime.fromisoformat(fe) if fe else None),
                        protocolo=structured.get("protocolo"),
                        admision_num=structured.get("admision_num"),
                    )
                )
                db.commit()
            except Exception:
                db.rollback()
                adm_id = None

    return pid, adm_id

async def _maybe_ai_enrich(text: str) -> Optional[Dict[str, Any]]:
    if not GeminiAIService:
        return None
    try:
        ai = GeminiAIService()
        prompt = f"""
Eres un médico clínico. A partir del texto de una HCE, extrae (en JSON estricto) los campos:

{{
  "motivo_internacion": "",
  "diagnostico_principal_cie10": "",
  "evolucion": "",
  "procedimientos": [],
  "interconsultas": [],
  "medicacion": [{{"farmaco":"","dosis":"","via":"","frecuencia":""}}],
  "indicaciones_alta": [],
  "recomendaciones": []
}}

Responde SOLO el JSON. Texto HCE:
\"\"\"{text[:150000]}\"\"\""""
        raw = await ai.generate_epc(prompt)
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except Exception:
                return None
        if isinstance(raw, dict):
            return raw
        return None
    except Exception:
        return None


# ----------------- endpoints -----------------
@router.post("/upload")
async def upload_hce(
    file: UploadFile = File(...),
    patient_id: Optional[str] = Form(None),
    admission_id: Optional[str] = Form(None),
    use_ai: bool = Form(True),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Adjuntá un PDF (.pdf).")

    saved_path = save_upload(file.filename, file.file)
    text, pages = extract_text_from_hce(saved_path)
    if not text.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No se pudo extraer texto del PDF.")

    structured = parse_hce_text(text)

    pid, adm_id = _ensure_patient_and_admission(db, patient_id=patient_id, structured=structured)
    if admission_id:
        adm_id = admission_id

    ai_data: Optional[Dict[str, Any]] = await _maybe_ai_enrich(text) if use_ai else None

    doc = {
        "patient_id": pid,
        "admission_id": adm_id,
        "text": text,
        "pages": pages,
        "structured": structured,
        "ai_generated": ai_data,
        "source": {
            "filename": file.filename,
            "saved_basename": saved_path.name,
            "content_type": file.content_type,
        },
        "created_by": user["id"],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    ins = await mongo.hce_docs.insert_one(doc)

    return {
        "ok": True,
        "hce_id": str(ins.inserted_id),
        "patient_id": pid,
        "admission_id": adm_id,
        "pages": pages,
        "structured": structured,
        "ai_generated": ai_data,
    }

@router.get("/{hce_id}")
async def get_hce(hce_id: str, include_text: bool = False):
    doc = await mongo.hce_docs.find_one({"_id": _to_oid(hce_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="HCE no encontrada")
    if not include_text and "text" in doc:
        doc = {**doc, "text": f"[{len(doc['text'])} chars]"}
    doc["_id"] = str(doc["_id"])
    return doc