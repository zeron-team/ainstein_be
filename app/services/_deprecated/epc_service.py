# backend/app/services/epc_service.py

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
from app.core.config import settings

# RAG Service for advanced generation with embeddings
try:
    from app.services.rag_service import RAGService, generate_epc_smart
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False

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

    # ========================= TEXTO HCE =========================
    @staticmethod
    def _pick_best_hce_text(doc: Dict[str, Any]) -> str:
        if not doc:
            return ""
        if isinstance(doc.get("text"), str) and doc["text"].strip():
            return doc["text"]

        structured = doc.get("structured") or {}
        if isinstance(structured, dict):
            for key in ("texto_completo", "texto", "descripcion"):
                val = structured.get(key)
                if isinstance(val, str) and val.strip():
                    return val

        if isinstance(doc.get("raw_text"), str) and doc["raw_text"].strip():
            return doc["raw_text"]

        for k in ("content", "body", "contenido"):
            v = doc.get(k)
            if isinstance(v, str) and v.strip():
                return v

        return ""

    @classmethod
    def _extract_hce_text(cls, hce_doc: Dict[str, Any]) -> str:
        base = cls._pick_best_hce_text(hce_doc)
        if base:
            return base

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
        return "\n\n".join(p for p in parts if p).strip()

    @staticmethod
    def _rx_ci(val: str) -> Dict[str, Any]:
        esc = re.escape(val)
        esc = re.sub(r"\\\s+", r"\\s+", esc)
        return {"$regex": esc, "$options": "i"}

    @staticmethod
    def _uuid_variants(u: Optional[str]) -> List[Any]:
        out: List[Any] = []
        if not u:
            return out
        out.append(u)
        try:
            _uuid = UUID(u)
            out.append(Binary(_uuid.bytes, UUID_SUBTYPE))
        except Exception:
            pass
        return out

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

    async def _fetch_latest_hce(self, *, patient_id: str, admission_id: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        IMPORTANTE:
        - Evita devolver HCE "genérica" o de otro paciente.
        - Evita fallback global "sin asignar" fuera de ventana.
        - Requiere texto útil mínimo para que la IA no 'invente'.
        """
        collections = await pick_hce_collections()

        patient_variants = self._uuid_variants(patient_id)
        adm_variants = self._uuid_variants(admission_id) if admission_id else []

        window_minutes = int(getattr(settings, "EPC_HCE_LOOKBACK_MINUTES", 60))
        now_utc = datetime.utcnow()
        window_start = now_utc - timedelta(minutes=window_minutes)
        recent_by_oid = {"_id": {"$gte": ObjectId.from_datetime(window_start)}}
        recent_or_created = {"$or": [{"created_at": {"$gte": window_start}}, recent_by_oid]}

        patient = self._get_patient_safe(patient_id)
        dni = (getattr(patient, "dni", None) or "").strip() if patient else ""
        cuil = (getattr(patient, "cuil", None) or "").strip() if patient else ""
        apellido = (getattr(patient, "apellido", None) or "").strip()
        nombre = (getattr(patient, "nombre", None) or "").strip()

        def _has_text(doc: Dict[str, Any]) -> bool:
            txt = self._extract_hce_text(doc) or ""
            min_chars = int(getattr(settings, "EPC_HCE_MIN_TEXT_CHARS", 80))
            return len(txt.strip()) >= min_chars

        def _log_try(coll_name: str, title: str, filt: Dict[str, Any]) -> None:
            log.debug("[HCE-LOOKUP] %s [%s] = %s", title, coll_name, filt)

        # A) por IDs (con campos alternativos)
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

            and_terms: List[Dict[str, Any]] = [{"$or": or_terms}]

            if adm_variants:
                adm_or: List[Dict[str, Any]] = []
                for av in adm_variants:
                    adm_or += [
                        {"admission_id": av},
                        {"admission.id": av},
                        {"admision_id": av},
                        {"admision.id": av},
                        {"admissionId": av},
                    ]
                and_terms.append({"$or": adm_or})

            filt_a: Dict[str, Any] = {"$and": and_terms}
            _log_try(coll.name, "A (patient/admission robust)", filt_a)
            doc = await coll.find_one(filt_a, sort=[("created_at", -1), ("_id", -1)])
            if doc and _has_text(doc):
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
                    if doc and _has_text(doc):
                        return doc

        # C) apellido/nombre (ventana) - solo si hay texto (evita matches vacíos)
        if apellido or nombre:
            for coll in collections:
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

                if not doc:
                    and_terms_rx: List[Dict[str, Any]] = [recent_or_created]
                    if apellido:
                        and_terms_rx.append({"text": self._rx_ci(apellido)})
                    if nombre:
                        and_terms_rx.append({"text": self._rx_ci(nombre)})
                    filt_c1_rx = {"$and": and_terms_rx}
                    _log_try(coll.name, "C1/regex", filt_c1_rx)
                    doc = await coll.find_one(filt_c1_rx, sort=[("created_at", -1), ("_id", -1)])

                if doc:
                    if not doc.get("patient_id"):
                        await coll.update_one({"_id": doc["_id"]}, {"$set": {"patient_id": patient_id}})
                        doc = await coll.find_one({"_id": doc["_id"]})
                    if doc and _has_text(doc):
                        return doc

        # D) fallback "sin asignar" SOLO EN VENTANA (evita tomar la última HCE de otro)
        allow_unassigned = bool(getattr(settings, "EPC_WS_FALLBACK_UNASSIGNED", False))
        if allow_unassigned:
            for coll in collections:
                filt_d1 = {
                    "$and": [
                        recent_or_created,
                        {
                            "$or": [
                                {"patient_id": {"$exists": False}},
                                {"patient_id": ""},
                                {"patient_id": None},
                            ]
                        },
                    ]
                }
                _log_try(coll.name, "D1 (sin asignar + ventana)", filt_d1)
                doc = await coll.find_one(filt_d1, sort=[("created_at", -1), ("_id", -1)])
                if doc:
                    await coll.update_one({"_id": doc["_id"]}, {"$set": {"patient_id": patient_id}})
                    doc = await coll.find_one({"_id": doc["_id"]})
                    if doc and _has_text(doc):
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
                detail=(
                    "No se encontró HCE vinculable para este paciente. "
                    "Verifique que la ingesta del WS guarde patient_id o dni/cuil, "
                    "y que exista texto clínico real (no vacío)."
                ),
            )

        hce_text: str = self._extract_hce_text(hce) or ""
        pages: int = int(hce.get("pages") or 0)

        min_chars = int(getattr(settings, "EPC_HCE_MIN_TEXT_CHARS", 80))
        if len(hce_text.strip()) < min_chars:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"HCE encontrada pero sin texto clínico útil (len={len(hce_text.strip())}, min={min_chars}). "
                    "Se bloquea generación para evitar EPC 'inventada'."
                ),
            )

        prompt = self._build_prompt(hce_text=hce_text, pages=pages)

        # ✅ Use RAG service when enabled, fallback to legacy
        use_rag = RAG_AVAILABLE and getattr(settings, 'RAG_ENABLED', False)
        
        if use_rag:
            log.info("[EPCService.generate] Using RAG service with embeddings")
            try:
                content = await generate_epc_smart(
                    hce_text=hce_text,
                    patient_id=row.patient_id,
                    pages=pages,
                    use_rag=True,
                    fallback_to_legacy=True,
                )
            except Exception as e:
                log.warning("[EPCService.generate] RAG failed, using legacy: %s", e)
                ai = GeminiAIService()
                content = await ai.generate_epc(prompt)
        else:
            log.info("[EPCService.generate] Using legacy GeminiAIService")
            ai = GeminiAIService()
            content = await ai.generate_epc(prompt)

        # ⚠️ POST-PROCESAMIENTO OBLIGATORIO: Asegurar cumplimiento de reglas
        # Importar aquí para evitar circular imports
        from app.services.ai_langchain_service import _post_process_epc_result
        import json as json_module
        import re
        
        # El content puede tener estructura {"json": {...}}, {"raw_text": "..."} o ser directo
        if isinstance(content, dict):
            log.info(f"[EPCService] Content keys: {list(content.keys())}")
            
            try:
                if "json" in content and isinstance(content["json"], dict):
                    # Caso normal: ya tiene JSON parseado
                    content["json"] = _post_process_epc_result(content["json"])
                    log.info("[EPCService] Post-procesamiento aplicado a content.json")
                    
                elif "raw_text" in content:
                    # Caso fallback: Gemini devolvió texto que necesita parsing
                    raw = content["raw_text"]
                    log.warning("[EPCService] Recibido raw_text, intentando parsear JSON")
                    
                    # Intentar parsear directamente (si raw_text ES el JSON)
                    parsed = None
                    
                    # Primero intentar parsear directamente
                    try:
                        # Limpiar el texto (quitar backticks si hay)
                        clean_text = raw.strip()
                        if clean_text.startswith("```"):
                            # Quitar bloque de código markdown
                            lines = clean_text.split("\n")
                            # Quitar primera y última línea si son ```
                            if lines[0].startswith("```"):
                                lines = lines[1:]
                            if lines and lines[-1].strip() == "```":
                                lines = lines[:-1]
                            clean_text = "\n".join(lines)
                        
                        # Intentar parsear
                        if clean_text.strip().startswith("{"):
                            parsed = json_module.loads(clean_text)
                            log.info("[EPCService] JSON parseado directamente desde raw_text")
                    except json_module.JSONDecodeError:
                        pass
                    
                    # Si no funcionó, buscar con regex más robusto
                    if parsed is None:
                        # Buscar desde el primer { hasta el último }
                        start_idx = raw.find("{")
                        end_idx = raw.rfind("}")
                        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                            json_str = raw[start_idx:end_idx+1]
                            try:
                                parsed = json_module.loads(json_str)
                                log.info("[EPCService] JSON extraído con índices desde raw_text")
                            except json_module.JSONDecodeError as je:
                                log.error(f"[EPCService] No se pudo parsear JSON: {je}")
                    
                    if parsed and isinstance(parsed, dict):
                        parsed = _post_process_epc_result(parsed)
                        content["json"] = parsed
                        log.info("[EPCService] JSON parseado y post-procesado desde raw_text")
                    else:
                        log.error("[EPCService] No se pudo extraer JSON válido de raw_text")
                        
                else:
                    # Caso legacy: el dict es directamente el contenido
                    content = _post_process_epc_result(content)
                    log.info("[EPCService] Post-procesamiento aplicado directo a content")
                    
            except Exception as pp_err:
                log.error(f"[EPCService] Error en post-procesamiento: {pp_err}")
        else:
            log.warning(f"[EPCService] Content no es dict, tipo: {type(content)}")
        
        # ✅ CORRECCIÓN: versiones van a epc_versions (no epc_docs)
        version_doc = {
            "epc_id": row.id,
            "patient_id": row.patient_id,
            "admission_id": row.admission_id,
            "source_hce_id": str(hce.get("_id")) if hce and hce.get("_id") else None,
            "generated_at": datetime.utcnow(),
            "content": content,
        }
        
        # DEBUG: Log del content antes de guardar
        log.warning(f"[EPCService] Guardando version, content keys: {list(content.keys()) if isinstance(content, dict) else 'no-dict'}")
        if isinstance(content, dict) and "json" in content:
            log.warning(f"[EPCService] content.json keys: {list(content['json'].keys()) if isinstance(content['json'], dict) else 'no-dict'}")
        
        ins = await mongo.epc_versions.insert_one(version_doc)

        row.version_actual_oid = str(ins.inserted_id)
        row.estado = "validada"
        row.fecha_emision = datetime.utcnow()
        self.db.commit()

        try:
            self.patient_repo.upsert_status(
                row.patient_id,
                estado=PatientEstado.epc_generada.value,
                observaciones=None,
            )
        except Exception as e:
            log.warning("No se pudo actualizar estado del paciente: %s", e)

        return {
            "id": row.id,
            "estado": row.estado,
            "version_actual_oid": row.version_actual_oid,
            "content": content,
        }

    async def get_latest_content(self, *, epc_id: str) -> Dict[str, Any]:
        doc = await mongo.epc_versions.find_one(
            {"epc_id": epc_id},
            sort=[("generated_at", -1), ("_id", -1)],
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Sin contenido generado para esta EPC")
        return {
            "epc_id": epc_id,
            "source_hce_id": (str(doc.get("source_hce_id")) if doc.get("source_hce_id") else None),
            "generated_at": (doc.get("generated_at").isoformat() + "Z") if doc.get("generated_at") else None,
            "content": doc.get("content"),
        }

    async def list_versions(self, *, epc_id: str) -> List[Dict[str, Any]]:
        cur = mongo.epc_versions.find({"epc_id": epc_id}).sort([("generated_at", -1), ("_id", -1)])
        out: List[Dict[str, Any]] = []
        async for d in cur:
            out.append(
                {
                    "id": str(d.get("_id")),
                    "source_hce_id": (str(d.get("source_hce_id")) if d.get("source_hce_id") else None),
                    "generated_at": (d.get("generated_at").isoformat() + "Z") if d.get("generated_at") else None,
                }
            )
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