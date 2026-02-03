from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from io import BytesIO
from uuid import uuid4
from starlette.concurrency import run_in_threadpool

from app.core.deps import get_db, role_required
from app.services.patient_service import PatientService
from app.domain.schemas import PatientCreate, PatientOut, HceImportResponse
from app.domain.enums import PatientEstado
from app.repositories.patient_repo import PatientRepo
from app.adapters.mongo_client import db as mongo
from app.services.hce_parser import save_upload, extract_text_from_hce
from app.services.ai_gemini_service import GeminiAIService

router = APIRouter(prefix="/patients", tags=["Patients"])

# ---------------------------
# Listado con búsqueda, estado y paginación
# ---------------------------
@router.get("", dependencies=[Depends(role_required("admin", "medico"))])
async def list_patients(
    q: str | None = None,
    estado: str | None = Query(
        default=None,
        description="Filtra por estado del paciente: internacion | falta_epc | epc_generada | alta",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    svc = PatientService(db)
    result = svc.list(q=q, estado=estado, page=page, page_size=page_size)
    
    # Enriquecer con datos de EPC y HCE desde MongoDB
    patient_ids = [item["id"] for item in result["items"]]
    if patient_ids:
        # 1. Buscar la EPC más reciente para cada paciente
        epc_pipeline = [
            {"$match": {"patient_id": {"$in": patient_ids}}},
            {"$sort": {"created_at": -1}},
            {"$group": {
                "_id": "$patient_id",
                "created_by": {"$first": "$created_by"},
                "created_by_name": {"$first": "$created_by_name"},
                "created_at": {"$first": "$created_at"},
            }},
        ]
        epc_data = {}
        async for doc in mongo.epc_docs.aggregate(epc_pipeline):
            epc_data[doc["_id"]] = {
                "epc_created_by_name": doc.get("created_by_name"),
                "epc_created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
            }

        # 2. Buscar la HCE más reciente (para fechas precisas y tipo de alta)
        hce_pipeline = [
            {"$match": {"patient_id": {"$in": patient_ids}}},
            {"$sort": {"created_at": -1}}, # Ultima HCE importada
            {"$group": {
                "_id": "$patient_id",
                "structured": {"$first": "$structured"},
                "ainstein": {"$first": "$ainstein"},
            }},
        ]
        hce_data = {}
        async for doc in mongo.hce_docs.aggregate(hce_pipeline):
            hce_data[doc["_id"]] = {
                "structured": doc.get("structured") or {},
                "ainstein": doc.get("ainstein") or {},
            }
        
        # Enriquecer items
        for item in result["items"]:
            pid = item["id"]
            
            # EPC Info
            epc_info = epc_data.get(pid, {})
            item["epc_created_by_name"] = epc_info.get("epc_created_by_name")
            item["epc_created_at"] = epc_info.get("epc_created_at")

            # HCE Info (Dates & Discharge)
            if pid in hce_data:
                h_struc = hce_data[pid]["structured"]
                h_ainstein = hce_data[pid]["ainstein"]
                
                # Fechas desde Mongo (Structured o Ainstein directo)
                raw_ingreso = h_struc.get("fecha_ingreso")
                raw_egreso = h_struc.get("fecha_egreso_original") or h_struc.get("fecha_egreso")
                
                # Tipo de Alta
                t_alta = h_struc.get("tipo_alta") or \
                         (h_ainstein.get("episodio") or {}).get("taltDescripcion")

                # Edad (Directo de Ainstein o calculado en structured)
                age = h_struc.get("edad") or (h_ainstein.get("episodio") or {}).get("paciEdad")

                # Movimiento (inteCodigo)
                mov_id = (h_ainstein.get("episodio") or {}).get("inteCodigo") or \
                         (h_ainstein.get("inteCodigo"))
                
                if raw_ingreso:
                    item["fecha_ingreso"] = str(raw_ingreso)
                if raw_egreso:
                    item["fecha_egreso"] = str(raw_egreso)
                if t_alta:
                    item["tipo_alta"] = str(t_alta)
                if age:
                    item["edad"] = age
                if mov_id:
                    item["movimiento_id"] = str(mov_id)
                
                # Recalcular días si tenemos fecha ingreso nueva
                # Intentamos parsear para calculo
                if item.get("fecha_ingreso"):
                    try:
                        # Soportar ISO y formatos comunes de str
                        fi_str = str(item["fecha_ingreso"]).replace("T", " ").split(".")[0]
                        fmt = "%Y-%m-%d %H:%M:%S" if " " in fi_str else "%Y-%m-%d"
                        dt_ingreso = datetime.strptime(fi_str, fmt)
                        
                        dt_egreso = datetime.utcnow()
                        if item.get("fecha_egreso"):
                            fe_str = str(item["fecha_egreso"]).replace("T", " ").split(".")[0]
                            dt_egreso = datetime.strptime(fe_str, fmt)
                        
                        dias = (dt_egreso - dt_ingreso).days
                        item["dias_estada"] = dias
                    except Exception:
                        pass # Si falla parseo, mantenemos lo que calculó el repo (o nada)

    return result

# ---------------------------
# Get by ID
# ---------------------------
@router.get(
    "/{patient_id}",
    response_model=PatientOut,
    dependencies=[Depends(role_required("admin", "medico"))],
)
def get_patient(patient_id: str, db: Session = Depends(get_db)):
    svc = PatientService(db)
    return svc.get_by_id(patient_id)

# ---------------------------
# Update
# ---------------------------
@router.put(
    "/{patient_id}",
    response_model=PatientOut,
    dependencies=[Depends(role_required("admin"))],
)
def update_patient(patient_id: str, payload: PatientCreate, db: Session = Depends(get_db)):
    svc = PatientService(db)
    return svc.update(patient_id, payload.model_dump())

# ---------------------------
# Delete
# ---------------------------
@router.delete(
    "/{patient_id}",
    status_code=204,
    dependencies=[Depends(role_required("admin"))],
)
def delete_patient(patient_id: str, db: Session = Depends(get_db)):
    svc = PatientService(db)
    svc.delete(patient_id)
    return {"ok": True}

# ---------------------------
# Parse HCE (PDF) with AI
# ---------------------------
@router.post(
    "/parse-hce",
    dependencies=[Depends(role_required("admin", "medico"))],
)
async def parse_hce_for_patient_data(file: UploadFile = File(...)):
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="Debe adjuntar un PDF")

    try:
        pdf_bytes = await file.read()
        
        # Guardar PDF temporalmente
        tmp_name = f"HCE_{uuid4().hex}.pdf"
        # Como save_upload y extract_text no son async, las corremos en un threadpool
        path = await run_in_threadpool(save_upload, tmp_name, BytesIO(pdf_bytes))
        text, _ = await run_in_threadpool(extract_text_from_hce, path)

        # Usar IA para extraer datos
        ai = GeminiAIService()
        ai_extracted_data = await ai.extract_patient_data_from_hce(text)
        
        return ai_extracted_data

    except Exception as e:
        # log.error(f"Error parsing HCE file: {e}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail=f"No se pudo parsear el archivo PDF. Error: {e}",
        )

# ---------------------------
# Alta manual
# ---------------------------
@router.post(
    "",
    response_model=PatientOut,
    dependencies=[Depends(role_required("admin", "medico"))],
)
def create_patient_manual(payload: PatientCreate, db: Session = Depends(get_db)):
    svc = PatientService(db)
    patient, _ = svc.create_manual(payload.model_dump(), created_by="system")

    # Estado inicial: internación
    PatientRepo(db).upsert_status(
        patient["id"],
        estado=PatientEstado.internacion.value,
        observaciones=None,
    )

    return patient

# ---------------------------
# Alta por HCE (PDF)
# ---------------------------
import logging

log = logging.getLogger(__name__)

@router.post(
    "/import-hce",
    response_model=HceImportResponse,
    dependencies=[Depends(role_required("admin", "medico"))],
)
async def import_patient_from_hce(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    log.debug("Entering import_patient_from_hce endpoint.")
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="Debe adjuntar un PDF")

    try:
        pdf_bytes = await file.read()
        svc = PatientService(db)
        patient, admission, text_preview, pages, source_filename = await svc.create_from_hce(
            pdf_bytes,
            created_by="system",
        )

        # Estado inicial: internación
        PatientRepo(db).upsert_status(
            patient["id"],
            estado=PatientEstado.internacion.value,
            observaciones=None,
        )

        # Aseguramos persistencia de la HCE en Mongo (id de admisión viene como dict en el service)
        admission_id = admission.get("id") if isinstance(admission, dict) else getattr(admission, "id", None)

        hce_doc = {
            "patient_id": patient["id"],
            "admission_id": admission_id,
            "text": text_preview,          # preview; el full ya lo guarda el service; esto es ensure
            "pages": pages,
            "source_filename": source_filename,
            "created_at": datetime.utcnow(),
            "source": "upload",
        }
        await mongo.hce_docs.update_one(
            {
                "patient_id": hce_doc["patient_id"],
                "admission_id": hce_doc["admission_id"],
                "source_filename": source_filename,
            },
            {"$setOnInsert": hce_doc},
            upsert=True,
        )

        return HceImportResponse(
            status="created",
            patient=patient,
            admission=admission,
            hce_text_preview=text_preview,
            pages=pages,
            source_filename=source_filename,
            message="Paciente importado desde HCE",
        )
    except Exception as e:
        # Log the full error for debugging
        # log.error(f"Error processing HCE file: {e}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail=f"No se pudo procesar el archivo PDF. Error: {e}",
        )