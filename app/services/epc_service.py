from __future__ import annotations

import logging
import re
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from bson.objectid import ObjectId
from bson.binary import Binary, UUID_SUBTYPE
from pymongo.errors import OperationFailure

from app.repositories.epc_repo import EPCRepo
from app.repositories.patient_repo import PatientRepo
from app.domain.enums import PatientEstado
from app.domain.schemas import EPCOut
from app.adapters.mongo_client import db as mongo
from app.adapters.mongo_client import pick_hce_collections
from app.services.ai_gemini_service import GeminiAIService

try:
    from app.domain.models import Patient as PatientModel  # type: ignore
except Exception:
    PatientModel = None  # type: ignore

log = logging.getLogger(__name__)


class EPCService:
    def __init__(self, db: Session):
        self.db = db
        self.epc_repo = EPCRepo(db)
        self.patient_repo = PatientRepo(db)

    def get_by_id(self, epc_id: str) -> EPCOut:
        row = self.epc_repo.get(epc_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="EPC no encontrado")
        return EPCOut(
            id=row.id,
            patient_id=row.patient_id,
            admission_id=row.admission_id,
            estado=row.estado,
            titulo=row.titulo,
            diagnostico_principal_cie10=row.diagnostico_principal_cie10,
            fecha_emision=row.fecha_emision.isoformat() if row.fecha_emision else None,
            medico_responsable=row.medico_responsable,
            firmado_por_medico=row.firmado_por_medico,
            motivo_internacion=None,
            evolucion=None,
            procedimientos=None,
            interconsultas=None,
            medicacion=None,
            indicaciones_alta=None,
            recomendaciones=None,
        )

    def update(self, epc_id: str, payload: dict) -> EPCOut:
        epc = self.epc_repo.update(epc_id, payload)
        if not epc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="EPC no encontrado")
        return self.get_by_id(epc_id)

    def open_or_create(self, *, patient_id: str, admission_id: Optional[str], created_by: str) -> EPCOut:
        row = self.epc_repo.get_by_patient_adm(patient_id, admission_id)
        if not row:
            row = self.epc_repo.create(patient_id=patient_id, admission_id=admission_id, created_by=created_by)
        return EPCOut(
            id=row.id,
            patient_id=row.patient_id,
            admission_id=row.admission_id,
            estado=row.estado,
            titulo=row.titulo,
            diagnostico_principal_cie10=row.diagnostico_principal_cie10,
            fecha_emision=row.fecha_emision.isoformat() if row.fecha_emision else None,
            medico_responsable=row.medico_responsable,
            firmado_por_medico=row.firmado_por_medico,
            motivo_internacion=None,
            evolucion=None,
            procedimientos=None,
            interconsultas=None,
            medicacion=None,
            indicaciones_alta=None,
            recomendaciones=None,
        )

    # ========================= LOOKUP DE HCE =========================
    def _get_patient_safe(self, patient_id: str):
        try:
            p = self.patient_repo.get(patient_id)  # type: ignore[attr-defined]
            if p:
                return p
        except Exception:
            pass
        if PatientModel is not None:
            try:
                return self.db.get(PatientModel, patient_id)
            except Exception:
                return None
        return None

    @staticmethod
    def _rx_ci(val: str) -> Dict[str, Any]:
        esc = re.escape(val)
        esc = re.sub(r"\\\s+", r"\\s+", esc)
        return {"$regex": esc, "$options": "i"}

    @staticmethod
    def _uuid_variants(u: str) -> List[Any]:
        out: List[Any] = [u]
        try:
            _uuid = UUID(u)
            out.append(Binary(_uuid.bytes, UUID_SUBTYPE))
        except Exception:
            pass
        return out

    async def _fetch_latest_hce(self, *, patient_id: str, admission_id: Optional[str]) -> Optional[Dict[str, Any]]:
        collections = await pick_hce_collections()

        patient_variants = self._uuid_variants(patient_id)
        adm_variants = self._uuid_variants(admission_id) if admission_id else []

        window_minutes = 20
        now_utc = datetime.utcnow()
        window_start = now_utc - timedelta(minutes=window_minutes)
        recent_by_oid = {"_id": {"$gte": ObjectId.from_datetime(window_start)}}
        recent_or_created = {"$or": [{"created_at": {"$gte": window_start}}, recent_by_oid]}

        patient = self._get_patient_safe(patient_id)
        dni = (getattr(patient, "dni", None) or "").strip() if patient else ""
        cuil = (getattr(patient, "cuil", None) or "").strip() if patient else ""
        apellido = (getattr(patient, "apellido", None) or "").strip()
        nombre = (getattr(patient, "nombre", None) or "").strip()

        def _log_try(coll_name: str, title: str, filt: Dict[str, Any]) -> None:
            log.debug("[HCE-LOOKUP] %s [%s] = %s", title, coll_name, filt)

        # A) por IDs
        for coll in collections:
            or_terms: List[Dict[str, Any]] = []
            for v in patient_variants:
                or_terms += [
                    {"patient_id": v},
                    {"patient.id": v},
                    {"patientId": v},
                    {"paciente_id": v},
                    {"paciente.id": v},
                ]
            if adm_variants:
                for av in adm_variants:
                    or_terms += [
                        {"admission_id": av},
                        {"admission.id": av},
                        {"admision_id": av},
                    ]
            filt_a: Dict[str, Any] = {"$or": or_terms}
            _log_try(coll.name, "A (patient/admission)", filt_a)
            doc = await coll.find_one(filt_a, sort=[("created_at", -1), ("_id", -1)])
            if doc:
                return doc

        # B) por DNI/CUIL
        if dni or cuil:
            for coll in collections:
                or_b: List[Dict[str, Any]] = []
                if dni:
                    or_b += [{"dni": dni}, {"patient.dni": dni}, {"paciente.dni": dni}]
                if cuil:
                    or_b += [{"cuil": cuil}, {"patient.cuil": cuil}, {"paciente.cuil": cuil}]
                filt_b = {"$or": or_b}
                _log_try(coll.name, "B (dni/cuil)", filt_b)
                doc = await coll.find_one(filt_b, sort=[("created_at", -1), ("_id", -1)])
                if doc:
                    if not doc.get("patient_id"):
                        await coll.update_one({"_id": doc["_id"]}, {"$set": {"patient_id": patient_id}})
                        doc = await coll.find_one({"_id": doc["_id"]})
                    return doc

        # C1) apellido/nombre con ventana
        if apellido or nombre:
            for coll in collections:
                # $text si existe índice
                try:
                    if apellido and nombre:
                        filt_c1 = {"$and": [recent_or_created, {"$text": {"$search": f"\"{apellido}\" \"{nombre}\""}}]}
                    elif apellido:
                        filt_c1 = {"$and": [recent_or_created, {"$text": {"$search": f"\"{apellido}\""}}]}
                    else:
                        filt_c1 = {"$and": [recent_or_created, {"$text": {"$search": f"\"{nombre}\""}}]}
                    _log_try(coll.name, "C1/$text", filt_c1)
                    doc = await coll.find_one(filt_c1, sort=[("created_at", -1), ("_id", -1)])
                except OperationFailure:
                    doc = None

                # regex fallback
                if not doc:
                    and_terms: List[Dict[str, Any]] = [recent_or_created]
                    if apellido:
                        and_terms.append({"text": self._rx_ci(apellido)})
                    if nombre:
                        and_terms.append({"text": self._rx_ci(nombre)})
                    filt_c1_rx = {"$and": and_terms}
                    _log_try(coll.name, "C1/regex", filt_c1_rx)
                    doc = await coll.find_one(filt_c1_rx, sort=[("created_at", -1), ("_id", -1)])

                if doc:
                    if not doc.get("patient_id"):
                        await coll.update_one({"_id": doc["_id"]}, {"$set": {"patient_id": patient_id}})
                        doc = await coll.find_one({"_id": doc["_id"]})
                    return doc

            # C2) sin ventana
            for coll in collections:
                try:
                    if apellido and nombre:
                        filt_c2 = {"$text": {"$search": f"\"{apellido}\" \"{nombre}\""}}
                    elif apellido:
                        filt_c2 = {"$text": {"$search": f"\"{apellido}\""}}
                    else:
                        filt_c2 = {"$text": {"$search": f"\"{nombre}\""}}
                    _log_try(coll.name, "C2/$text", filt_c2)
                    doc = await coll.find_one(filt_c2, sort=[("created_at", -1), ("_id", -1)])
                except OperationFailure:
                    doc = None

                if not doc:
                    and_terms_rx: List[Dict[str, Any]] = []
                    if apellido:
                        and_terms_rx.append({"text": self._rx_ci(apellido)})
                    if nombre:
                        and_terms_rx.append({"text": self._rx_ci(nombre)})
                    filt_c2_rx = {"$and": and_terms_rx} if and_terms_rx else {}
                    _log_try(coll.name, "C2/regex", filt_c2_rx)
                    doc = await coll.find_one(filt_c2_rx, sort=[("created_at", -1), ("_id", -1)])

                if doc:
                    if not doc.get("patient_id"):
                        await coll.update_one({"_id": doc["_id"]}, {"$set": {"patient_id": patient_id}})
                        doc = await coll.find_one({"_id": doc["_id"]})
                    return doc

        # D1) sin asignar + ventana
        for coll in collections:
            filt_d1 = {"$and": [recent_or_created, {"$or": [{"patient_id": {"$exists": False}}, {"patient_id": ""}, {"patient_id": None}]}]}
            _log_try(coll.name, "D1 (sin asignar + ventana)", filt_d1)
            doc = await coll.find_one(filt_d1, sort=[("created_at", -1), ("_id", -1)])
            if doc:
                await coll.update_one({"_id": doc["_id"]}, {"$set": {"patient_id": patient_id}})
                doc = await coll.find_one({"_id": doc["_id"]})
                return doc

        # D2) sin asignar global
        for coll in collections:
            filt_d2 = {"$or": [{"patient_id": {"$exists": False}}, {"patient_id": ""}, {"patient_id": None}]}
            _log_try(coll.name, "D2 (sin asignar global)", filt_d2)
            doc = await coll.find_one(filt_d2, sort=[("_id", -1)])
            if doc:
                await coll.update_one({"_id": doc["_id"]}, {"$set": {"patient_id": patient_id}})
                doc = await coll.find_one({"_id": doc["_id"]})
                return doc

        # E) Fallback ventana por _id
        for coll in collections:
            filt_e = {"_id": {"$gte": ObjectId.from_datetime(window_start)}}
            _log_try(coll.name, "E (fallback ventana por _id)", filt_e)
            doc = await coll.find_one(filt_e, sort=[("_id", -1)])
            if doc:
                await coll.update_one({"_id": doc["_id"]}, {"$set": {"patient_id": patient_id}})
                doc = await coll.find_one({"_id": doc["_id"]})
                log.debug("[HCE-LOOKUP] Fallback E usado en '%s': se vinculó la HCE más reciente en ventana.", coll.name)
                return doc

        return None

    async def generate(self, *, epc_id: str) -> Dict[str, Any]:
        row = self.epc_repo.get(epc_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="EPC no encontrado")

        log.debug("EPC generate: patient_id=%s, admission_id=%s", row.patient_id, row.admission_id)

        hce = await self._fetch_latest_hce(patient_id=row.patient_id, admission_id=row.admission_id)
        log.debug("HCE find_one result: %s", hce)

        if not hce:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=("No se encontró HCE vinculable para este paciente pese a intentar por "
                        "patient_id (texto/Binary), dni/cuil, nombre+apellido (ventana 20m), "
                        "HCE sin asignar y fallback por _id. "
                        "Reintente importar la HCE o verifique los datos del paciente.")
            )

        hce_text: str = hce.get("text") or ""
        pages: int = hce.get("pages") or 0

        prompt = self._build_prompt(hce_text=hce_text, pages=pages)

        ai = GeminiAIService()
        content = await ai.generate_epc(prompt)

        version_doc = {
            "epc_id": row.id,
            "patient_id": row.patient_id,
            "admission_id": row.admission_id,
            "source_hce_id": str(hce.get("_id")) if hce and hce.get("_id") else None,
            "generated_at": datetime.utcnow(),
            "content": content,
        }
        ins = await mongo.epc_docs.insert_one(version_doc)

        row.version_actual_oid = str(ins.inserted_id)
        row.estado = "validada"
        row.fecha_emision = datetime.utcnow()
        self.db.commit()

        try:
            self.patient_repo.upsert_status(row.patient_id, estado=PatientEstado.epc_generada.value, observaciones=None)
        except Exception as e:
            log.warning("No se pudo actualizar estado del paciente: %s", e)

        return {"id": row.id, "estado": row.estado, "version_actual_oid": row.version_actual_oid, "content": content}

    async def get_latest_content(self, *, epc_id: str) -> Dict[str, Any]:
        doc = await mongo.epc_docs.find_one({"epc_id": epc_id}, sort=[("generated_at", -1), ("_id", -1)])
        if not doc:
            raise HTTPException(status_code=404, detail="Sin contenido generado para esta EPC")
        return {
            "epc_id": epc_id,
            "source_hce_id": (str(doc.get("source_hce_id")) if doc.get("source_hce_id") else None),
            "generated_at": (doc.get("generated_at").isoformat() + "Z") if doc.get("generated_at") else None,
            "content": doc.get("content"),
        }

    async def list_versions(self, *, epc_id: str) -> List[Dict[str, Any]]:
        cur = mongo.epc_docs.find({"epc_id": epc_id}).sort([("generated_at", -1), ("_id", -1)])
        out: List[Dict[str, Any]] = []
        async for d in cur:
            out.append({
                "id": str(d.get("_id")),
                "source_hce_id": (str(d.get("source_hce_id")) if d.get("source_hce_id") else None),
                "generated_at": (d.get("generated_at").isoformat() + "Z") if d.get("generated_at") else None,
            })
        return out

    @staticmethod
    def _build_prompt(*, hce_text: str, pages: int) -> str:
        return f"""
Analiza el siguiente texto de una Historia Clínica Electrónica (HCE) y genera una EPICRISIS en formato JSON.

**Reglas estrictas:**
1.  Completa la siguiente estructura JSON usando **únicamente** información del texto de la HCE proporcionado.
2.  Responde **SOLO** con el objeto JSON. No incluyas texto adicional.
3.  Si un campo no se puede completar, usa "" o [] (no inventes).
4.  Idioma: español (Argentina).

{{
  "motivo_internacion": "...",
  "diagnostico_principal_cie10": "...",
  "evolucion": "...",
  "procedimientos": ["...", "..."],
  "interconsultas": ["...", "..."],
  "medicacion": [{{ "farmaco": "...", "dosis": "...", "via": "...", "frecuencia": "..." }}],
  "indicaciones_alta": ["...", "..."],
  "recomendaciones": ["...", "..."]
}}

**Texto HCE (páginas: {pages}):**
\"\"\"{hce_text}\"\"\"
"""