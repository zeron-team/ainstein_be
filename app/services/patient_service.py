from __future__ import annotations

import logging
from typing import Dict, Optional, Tuple
from sqlalchemy.orm import Session
from uuid import uuid4
from datetime import datetime
from io import BytesIO
import re

log = logging.getLogger(__name__)

from app.repositories.patient_repo import PatientRepo
from app.domain.enums import PatientEstado
from app.domain.models import Admission
from app.services.hce_parser import extract_text_from_hce, save_upload
from app.services.ai_gemini_service import GeminiAIService
from app.adapters.mongo_client import db as mongo
from fastapi import HTTPException


class PatientService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = PatientRepo(db)

    # ---------------------------
    # Listado con paginación
    # ---------------------------
    def list(self, *, q: Optional[str], estado: Optional[str], page: int, page_size: int) -> Dict:
        offset = (page - 1) * page_size
        items = self.repo.list(q=q, estado=estado, offset=offset, limit=page_size)
        total = self.repo.count(q=q, estado=estado)
        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total,
            "has_next": (offset + len(items)) < total,
            "has_prev": page > 1,
        }

    # ---------------------------
    # Get by ID
    # ---------------------------
    def get_by_id(self, patient_id: str) -> Patient:
        patient = self.repo.get(patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Paciente no encontrado")
        return patient

    # ---------------------------
    # Update
    # ---------------------------
    def update(self, patient_id: str, data: Dict) -> Patient:
        patient = self.repo.update(patient_id, data)
        if not patient:
            raise HTTPException(status_code=404, detail="Paciente no encontrado")
        return patient

    # ---------------------------
    # Delete
    # ---------------------------
    def delete(self, patient_id: str) -> None:
        deleted = self.repo.delete(patient_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Paciente no encontrado")

    # ---------------------------
    # Alta manual
    # ---------------------------
    def create_manual(self, data: Dict, *, created_by: str) -> Tuple[Dict, str]:
        row = self.repo.create(
            {
                "dni": data.get("dni"),
                "cuil": data.get("cuil"),
                "obra_social": data.get("obra_social"),
                "nro_beneficiario": data.get("nro_beneficiario"),
                "apellido": data["apellido"],
                "nombre": data["nombre"],
                "fecha_nacimiento": data.get("fecha_nacimiento"),
                "sexo": data.get("sexo"),
                "telefono": data.get("telefono"),
                "email": data.get("email"),
                "domicilio": data.get("domicilio"),
            }
        )
        # Estado inicial = internacion
        # Estado inicial = internacion
        self.repo.upsert_status(row.id, estado=PatientEstado.internacion.value, observaciones=None)

        # Si viene movimiento_id (Markey), crear la admisión asociada
        movimiento_id = data.get("movimiento_id")
        if movimiento_id:
            adm = Admission(
                id=str(uuid4()),
                patient_id=row.id,
                admision_num=str(movimiento_id),
                fecha_ingreso=datetime.utcnow(),
                estado="internacion"
            )
            self.db.add(adm)
            self.db.commit()

        patient_out = {
            "id": row.id,
            "apellido": row.apellido,
            "nombre": row.nombre,
            "dni": row.dni,
            "obra_social": row.obra_social,
            "nro_beneficiario": row.nro_beneficiario,
            "movimiento_id": movimiento_id,
        }
        return patient_out, PatientEstado.internacion.value

    # ---------------------------
    # Alta por HCE (PDF)
    # ---------------------------
    async def create_from_hce(self, pdf_bytes: bytes, *, created_by: str):
        log.debug("Entering create_from_hce method.")
        tmp_name = f"HCE_{uuid4().hex}.pdf"
        path = save_upload(tmp_name, file_obj=BytesIO(pdf_bytes))

        text, pages = extract_text_from_hce(path, max_chars=None)

        # Usar IA para extraer datos del paciente
        ai = GeminiAIService()
        ai_extracted_data = await ai.extract_patient_data_from_hce(text)

        # Validar datos mínimos de la IA
        apellido = ai_extracted_data.get("apellido")
        nombre = ai_extracted_data.get("nombre")
        if not apellido or not nombre:
            raise HTTPException(
                status_code=400,
                detail="La IA no pudo extraer el nombre y apellido del paciente de la HCE."
            )

        # Crear paciente con datos de la IA
        row = self.repo.create(
            {
                "apellido": apellido,
                "nombre": nombre,
                "dni": ai_extracted_data.get("dni"),
                "sexo": ai_extracted_data.get("sexo"),
                "fecha_nacimiento": ai_extracted_data.get("fecha_nacimiento"),
                "obra_social": ai_extracted_data.get("obra_social"),
                "nro_beneficiario": ai_extracted_data.get("nro_beneficiario"),
                "cuil": None, # No extraído por IA por ahora
            }
        )
        self.repo.upsert_status(row.id, estado=PatientEstado.internacion.value, observaciones="importado desde HCE con IA")

        adm = Admission(
            id=str(uuid4()),
            patient_id=row.id,
            sector=ai_extracted_data.get("sector"),
            habitacion=ai_extracted_data.get("habitacion"),
            cama=ai_extracted_data.get("cama"),
            fecha_ingreso=datetime.utcnow(), # Assuming admission date is current for now, or can be extracted if available
            fecha_egreso=None,
            protocolo=ai_extracted_data.get("protocolo"),
            admision_num=ai_extracted_data.get("admision_num"),
        )
        self.db.add(adm)
        self.db.commit()
        self.db.refresh(adm)

        doc = {
            "patient_id": row.id,
            "admission_id": adm.id,
            "source_filename": path.name,
            "pages": pages,
            "text": text,
            "created_at": datetime.utcnow(),
        }
        log.debug("Attempting to insert HCE document into MongoDB: %s", doc)
        try:
            await mongo.hce_docs.insert_one(doc)
            log.debug("HCE document inserted successfully.")
        except Exception as e:
            log.error("Error inserting HCE document into MongoDB: %s", e, exc_info=True)
            raise # Re-raise the exception to ensure it's caught by the router

        preview = text[:2000]
        patient_out = {
            "id": row.id,
            "apellido": row.apellido,
            "nombre": row.nombre,
            "dni": row.dni,
            "obra_social": row.obra_social,
            "nro_beneficiario": row.nro_beneficiario,
        }
        admission_out = {
            "id": adm.id,
            "patient_id": adm.patient_id,
            "sector": adm.sector,
            "fecha_ingreso": adm.fecha_ingreso.isoformat(),
        }

        return patient_out, admission_out, preview, pages, path.name