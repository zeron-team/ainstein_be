# app/routers/hce.py
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from bson import ObjectId
from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
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


def _parse_dt(v: Optional[str]) -> Optional[datetime]:
    if not v:
        return None
    try:
        # soporta "YYYY-MM-DDTHH:MM:SS" y "YYYY-MM-DD HH:MM:SS"
        return datetime.fromisoformat(str(v).replace("Z", "").strip())
    except Exception:
        return None


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

    # ✅ Si viene patient_id, aseguramos que exista en SQL (si no existe, lo creamos)
    if pid:
        found_by_id = db.query(Patient).filter(Patient.id == pid).first()
        if not found_by_id:
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

    # ✅ Si no viene patient_id, intentamos match por Apellido/Nombre y si no existe, creamos
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
                structured.get("estado_internacion"),
            ]
        )

        if tiene_algo:
            adm_id = str(uuid.uuid4())
            try:
                fi_raw = structured.get("fecha_ingreso")
                fi_dt = _parse_dt(fi_raw) or datetime.utcnow()

                # ✅ Para que figure como "Internación" activa:
                # dejamos fecha_egreso en NULL (aunque Ainstein traiga un egreso, lo guardamos aparte)
                fe_dt = None

                db.add(
                    Admission(
                        id=adm_id,
                        patient_id=pid,
                        sector=structured.get("sector"),
                        habitacion=structured.get("habitacion"),
                        cama=structured.get("cama"),
                        fecha_ingreso=fi_dt,
                        fecha_egreso=fe_dt,
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
\"\"\"{text}\"\"\""""
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


def _structured_from_ainstein(episodio: Dict[str, Any], historia: Any) -> Dict[str, Any]:
    inte_codigo = episodio.get("inteCodigo")
    paci_codigo = episodio.get("paciCodigo")

    # datos mínimos para que quede “internación” y EPC pueda generarse
    structured: Dict[str, Any] = {
        "paciente_apellido_nombre": f"AINSTEIN,{paci_codigo or 'SIN_CODIGO'}",
        "sexo": episodio.get("paciSexo"),
        "fecha_ingreso": (episodio.get("inteFechaIngreso") or ""),
        "fecha_egreso_original": (episodio.get("inteFechaEgreso") or ""),
        "sector": episodio.get("sector") or episodio.get("salaDescripcion"),
        "habitacion": episodio.get("habitacion"),
        "cama": episodio.get("cama"),
        "protocolo": episodio.get("protocolo"),
        "admision_num": str(inte_codigo) if inte_codigo is not None else None,
        "estado_internacion": "internacion",
        "ainstein": {
            "inteCodigo": inte_codigo,
            "paciCodigo": paci_codigo,
        },
        "ainstein_historia_count": len(historia) if isinstance(historia, list) else None,
    }

    return structured


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
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No se pudo extraer texto del PDF.",
        )

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


# ✅ OJO: este endpoint DEBE ir ANTES que "/{hce_id}"
@router.get("/latest")
async def get_latest_hce(
    patient_id: str = Query(..., description="ID del paciente (SQL)"),
    include_text: bool = Query(False, description="Si true, devuelve el texto completo"),
):
    """
    Devuelve el último documento de HCE (Mongo) para un patient_id.
    Usado por el frontend para el botón 'Ojo' (Leer HCE) en el listado de pacientes.
    """
    doc = await mongo.hce_docs.find_one(
        {"patient_id": patient_id},
        sort=[("created_at", -1)],
    )
    if not doc:
        raise HTTPException(status_code=404, detail="HCE no encontrada para este paciente")

    if not include_text and "text" in doc:
        doc["text"] = f"[{len(doc.get('text') or '')} chars]"

    doc["_id"] = str(doc["_id"])
    return doc


@router.get("/{hce_id}")
async def get_hce(hce_id: str, include_text: bool = False):
    doc = await mongo.hce_docs.find_one({"_id": _to_oid(hce_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="HCE no encontrada")
    if not include_text and "text" in doc:
        doc = {**doc, "text": f"[{len(doc.get('text') or '')} chars]"}
    doc["_id"] = str(doc["_id"])
    return doc


@router.post("/import/ainstein")
async def import_ainstein_hce(
    payload: Dict[str, Any] = Body(...),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Recibe { episodio, historia } desde el frontend y:
    - crea/asegura Patient + Admission (internación activa => fecha_egreso NULL)
    - guarda en MongoDB (hce_docs) 100% SIN TRUNCAR
    - aplica chunking y embeddings para RAG en Qdrant
    """
    episodio = payload.get("episodio")
    historia = payload.get("historia")

    patient_id = payload.get("patient_id")
    admission_id = payload.get("admission_id")
    use_ai = bool(payload.get("use_ai", False))
    apply_embeddings = bool(payload.get("apply_embeddings", True))  # Por defecto TRUE

    if not isinstance(episodio, dict):
        raise HTTPException(status_code=400, detail="Falta 'episodio' (objeto) en el body.")
    if historia is None:
        raise HTTPException(status_code=400, detail="Falta 'historia' en el body.")

    # ✅ patient_id estable si no te lo mandan (evita duplicados por paciCodigo)
    if not patient_id and episodio.get("paciCodigo") is not None:
        patient_id = f"AINSTEIN_{episodio.get('paciCodigo')}"

    structured = _structured_from_ainstein(episodio, historia)

    pid, adm_id = _ensure_patient_and_admission(db, patient_id=patient_id, structured=structured)
    if admission_id:
        adm_id = admission_id

    # =========================================================================
    # TEXTO COMPLETO 100% - SIN TRUNCAR
    # =========================================================================
    # Guardar historia completa como JSON para referencia
    historia_json = json.dumps(historia, ensure_ascii=False)
    
    # Texto liviano; la historia completa queda en "ainstein.historia"
    text_stub = json.dumps(
        {
            "source": "ainstein",
            "inteCodigo": episodio.get("inteCodigo"),
            "paciCodigo": episodio.get("paciCodigo"),
            "historia_chars": len(historia_json),
        },
        ensure_ascii=False,
    )

    # AI enrichment - SIN LÍMITE DE CARACTERES
    ai_data: Optional[Dict[str, Any]] = None
    if use_ai:
        # Usar TODO el texto sin truncar
        ai_text = historia_json  # 100% sin [:150000]
        ai_data = await _maybe_ai_enrich(ai_text)

    doc = {
        "patient_id": pid,
        "admission_id": adm_id,
        "text": text_stub,
        "pages": 0,
        "structured": structured,
        "ai_generated": ai_data,
        "source": {
            "type": "ainstein",
            "inteCodigo": episodio.get("inteCodigo"),
            "paciCodigo": episodio.get("paciCodigo"),
        },
        "ainstein": {
            "episodio": episodio,  # 100% completo
            "historia": historia,  # 100% completo SIN TRUNCAR
        },
        "created_by": user["id"],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

    ins = await mongo.hce_docs.insert_one(doc)
    hce_id = str(ins.inserted_id)
    
    # =========================================================================
    # CHUNKING + EMBEDDINGS PARA RAG (Qdrant)
    # =========================================================================
    embedding_result = {"status": "skipped", "chunks": 0}
    
    if apply_embeddings:
        try:
            from app.services.hce_ainstein_parser import HCEAinsteinParser
            from app.services.vector_service import get_vector_service
            
            # Parsear y chunkar
            parser = HCEAinsteinParser()
            chunks = parser.chunk_by_registry_type(historia, hce_id)
            
            if chunks:
                vector_service = get_vector_service()
                
                # Indexar cada chunk
                for i, chunk in enumerate(chunks):
                    chunk_id = f"{hce_id}_{chunk.tipo}_{i}"
                    await vector_service.add_hce_chunk(
                        chunk_id=chunk_id,
                        text=chunk.texto,
                        metadata={
                            "hce_id": hce_id,
                            "patient_id": pid,
                            "tipo": chunk.tipo,
                            "fecha": chunk.fecha or "",
                            "chunk_index": i,
                        },
                    )
                
                embedding_result = {"status": "ok", "chunks": len(chunks)}
                
        except Exception as e:
            embedding_result = {"status": "error", "error": str(e)}

    return {
        "ok": True,
        "hce_id": hce_id,
        "patient_id": pid,
        "admission_id": adm_id,
        "estado": "internacion",
        "historia_registros": len(historia) if isinstance(historia, list) else 0,
        "historia_chars": len(historia_json),
        "embeddings": embedding_result,
    }