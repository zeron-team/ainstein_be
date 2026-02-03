# app/routers/epc.py
from __future__ import annotations

import json
import uuid
import logging
import hashlib
from datetime import datetime, date
from typing import Any, Dict, Optional, List
from uuid import UUID

from bson import ObjectId
from bson.binary import Binary, UUID_SUBTYPE
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
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
from app.services.epc_history import log_epc_event, get_epc_history
from app.utils.epc_pdf import build_epicrisis_pdf

# =============================================================================
# IMPORTS DE SERVICIOS REFACTORIZADOS (SOLID)
# =============================================================================
from app.services.epc.helpers import (
    now as _now,
    uuid_str as _uuid_str,
    clean_str as _clean_str,
    parse_dt_maybe as _parse_dt_maybe,
    safe_objectid as _safe_objectid,
    uuid_variants as _uuid_variants,
    json_from_ai as _json_from_ai,
    actor_name as _actor_name,
    age_from_ymd as _age_from_ymd,
    list_to_lines as _list_to_lines,
)
from app.services.epc.hce_extractor import (
    HCEExtractor,
    extract_hce_text as _extract_hce_text,
    extract_clinical_data as _extract_clinical_data,
)
from app.services.epc.pdf_builder import (
    build_epc_pdf_payload as _epc_pdf_payload_from_context,
)
from app.services.epc.feedback_service import (
    EPCFeedbackService,
    FeedbackData,
    FeedbackValidationError,
    get_feedback_service,
)

log = logging.getLogger(__name__)

ESTADO_INTERNACION = "internacion"
ESTADO_EPC_GENERADA = "epc_generada"

router = APIRouter(prefix="/epc", tags=["EPC / Epicrisis"])


# =============================================================================
# HELPERS LEGACY (DEPRECADOS - usar imports de app.services.epc)
# Se mantienen temporalmente por compatibilidad, pero serán eliminados.
# =============================================================================
# NOTA: Las funciones _now, _uuid_str, _clean_str, etc. ahora se importan desde services/epc
#
# Funciones movidas a app/services/epc/helpers.py:
#   _clean_str, _parse_dt_maybe, _safe_objectid, _uuid_variants, _json_from_ai,
#   _actor_name, _age_from_ymd, _list_to_lines
#
# Funciones movidas a app/services/epc/hce_extractor.py:
#   _pick_best_hce_text, _extract_ainstein_text, _extract_hce_text
#
# Ver docs/REFACTORING_SOLID_CHANGELOG.md para detalles completos
# =============================================================================

# ELIMINADO: def _clean_str - ahora importado desde services/epc


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


def _uuid_variants(val: Optional[str]) -> List[Any]:
    """
    Devuelve variantes para matchear UUID guardado como:
    - string
    - Binary(UUID_SUBTYPE=4)
    """
    out: List[Any] = []
    if not val:
        return out
    out.append(val)
    try:
        u = UUID(str(val))
        out.append(Binary(u.bytes, UUID_SUBTYPE))
    except Exception:
        pass
    return out


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
    4) content / body / contenido (por integraciones WS)
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

    for k in ("content", "body", "contenido"):
        v = doc.get(k)
        if isinstance(v, str) and v.strip():
            return v

    return ""


def _extract_ainstein_text(hce_doc: Dict[str, Any]) -> str:
    """
    Extrae texto clínico de HCE importadas desde Ainstein.
    Procesa ainstein.historia y ainstein.episodio para construir
    un texto rico que la IA pueda usar para generar la EPC.
    """
    parts: List[str] = []

    ainstein = hce_doc.get("ainstein") or {}
    episodio = ainstein.get("episodio") or {}
    historia = ainstein.get("historia") or []

    # Datos del episodio
    if episodio:
        ep_parts: List[str] = ["=== DATOS DEL EPISODIO ==="]
        if episodio.get("taltDescripcion"):
            ep_parts.append(f"Tipo de alta: {episodio.get('taltDescripcion')}")
        if episodio.get("paciEdad"):
            ep_parts.append(f"Edad: {episodio.get('paciEdad')} años")
        if episodio.get("paciSexo"):
            ep_parts.append(f"Sexo: {episodio.get('paciSexo')}")
        if episodio.get("inteFechaIngreso"):
            ep_parts.append(f"Fecha ingreso: {episodio.get('inteFechaIngreso')}")
        if episodio.get("inteFechaEgreso"):
            ep_parts.append(f"Fecha egreso: {episodio.get('inteFechaEgreso')}")
        if episodio.get("inteDiasEstada"):
            ep_parts.append(f"Días de estadía: {episodio.get('inteDiasEstada')}")
        if len(ep_parts) > 1:
            parts.extend(ep_parts)

    # Procesar cada entrada de historia clínica
    for entrada in historia:
        if not isinstance(entrada, dict):
            continue

        tipo = entrada.get("entrTipoRegistro", "Registro")
        fecha = entrada.get("entrFechaAtencion", "")

        entry_parts: List[str] = [f"\n=== {tipo} ({fecha}) ==="]

        if entrada.get("entrMotivoConsulta"):
            entry_parts.append(f"Motivo de consulta: {entrada['entrMotivoConsulta']}")

        if entrada.get("entrEvolucion"):
            entry_parts.append(f"Evolución: {entrada['entrEvolucion']}")

        if entrada.get("entrPlan"):
            entry_parts.append(f"Plan: {entrada['entrPlan']}")

        # Diagnósticos
        diagnosticos = entrada.get("diagnosticos") or []
        if diagnosticos:
            dx_texts = [
                d.get("diagDescripcion")
                for d in diagnosticos
                if isinstance(d, dict) and d.get("diagDescripcion")
            ]
            if dx_texts:
                entry_parts.append(f"Diagnósticos: {', '.join(dx_texts)}")

        # Medicación / indicaciones farmacológicas
        medicacion = entrada.get("indicacionFarmacologica") or []
        if medicacion:
            med_texts: List[str] = []
            for m in medicacion:
                if not isinstance(m, dict):
                    continue
                farmaco = m.get("geneDescripcion", "")
                dosis = m.get("enmeDosis", "")
                unidad = m.get("tumeDescripcion", "")
                via = m.get("meviDescripcion", "")
                frec = m.get("mefrDescripcion", "")
                if farmaco:
                    med_str = f"{farmaco}"
                    if dosis:
                        med_str += f" {dosis}{unidad}"
                    if via:
                        med_str += f" {via}"
                    if frec:
                        med_str += f" {frec}"
                    med_texts.append(med_str.strip())
            if med_texts:
                entry_parts.append(f"Medicación: {'; '.join(med_texts)}")

        # Procedimientos
        procedimientos = entrada.get("indicacionProcedimientos") or []
        if procedimientos:
            proc_texts = [
                p.get("procDescripcion")
                for p in procedimientos
                if isinstance(p, dict) and p.get("procDescripcion")
            ]
            if proc_texts:
                entry_parts.append(f"Procedimientos: {', '.join(proc_texts)}")

        # Enfermería
        enfermeria = entrada.get("indicacionEnfermeria") or []
        if enfermeria:
            enf_texts = [
                e.get("indiDescripcion")
                for e in enfermeria
                if isinstance(e, dict) and e.get("indiDescripcion")
            ]
            if enf_texts:
                entry_parts.append(f"Indicaciones enfermería: {', '.join(enf_texts)}")

        # Plantillas (valores relevantes)
        plantillas = entrada.get("plantillas") or []
        for pl in plantillas:
            if not isinstance(pl, dict):
                continue
            grupo = pl.get("grupDescripcion", "")
            props = pl.get("propiedades") or []
            pl_values: List[str] = []
            for prop in props:
                if not isinstance(prop, dict):
                    continue
                val = prop.get("engpValor")
                if val and isinstance(val, str) and val.strip():
                    # Limpiar HTML básico si existe
                    clean_val = val.replace("<br>", " ").replace("<br/>", " ")
                    clean_val = " ".join(clean_val.split())
                    label = prop.get("grprDescripcion", "Campo")
                    pl_values.append(f"{label}: {clean_val}")
            if pl_values:
                if grupo:
                    entry_parts.append(f"[{grupo}]")
                entry_parts.extend(pl_values)

        # Solo agregar si hay contenido útil
        if len(entry_parts) > 1:
            parts.extend(entry_parts)

    return "\n".join(parts).strip()


def _extract_hce_text(hce_doc: Dict[str, Any]) -> str:
    """
    Devuelve texto "usable" para generar la EPC.
    Soporta HCE de PDF y de Ainstein (WS).
    """
    # 1) Primero intentar texto directo (funciona bien para PDFs)
    base_text = _pick_best_hce_text(hce_doc)
    if base_text and len(base_text.strip()) >= 80:
        return base_text

    # 2) Si no hay texto directo útil, verificar si es de Ainstein
    source = hce_doc.get("source") or {}
    ainstein_data = hce_doc.get("ainstein") or {}

    if source.get("type") == "ainstein" or ainstein_data.get("historia"):
        ainstein_text = _extract_ainstein_text(hce_doc)
        if ainstein_text and len(ainstein_text.strip()) >= 80:
            return ainstein_text

    # 3) Si base_text existe pero es corto, aún devolverlo
    if base_text:
        return base_text

    # 4) Fallback a campos estructurados
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
    if isinstance(s, dict):
        return s

    if not s:
        return {}

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


def _actor_name(user: Any) -> str:
    """
    Obtiene un nombre legible del usuario para el historial.

    Intenta, en este orden:
    - full_name
    - username
    - email
    Soporta tanto objetos SQLAlchemy/Pydantic como dicts.
    """
    if not user:
        return "sistema"

    for attr in ("full_name", "username", "email"):
        val = getattr(user, attr, None)
        if val:
            return str(val)

    if isinstance(user, dict):
        for key in ("full_name", "username", "email", "name"):
            val = user.get(key)
            if val:
                return str(val)

    return "sistema"


def _age_from_ymd(ymd: Optional[str]) -> Optional[int]:
    if not ymd:
        return None
    try:
        y, m, d = str(ymd).split("-")
        dob = date(int(y), int(m), int(d))
        today = date.today()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    except Exception:
        return None


def _list_to_lines(items: Any) -> str:
    """
    Convierte listas de strings/objetos a texto multilínea para PDF.
    - strings: "• item"
    - dict medicación: "• farmaco · dosis · via · frecuencia"
    - otros dict: intenta descripcion/detalle/resumen/especialidad o JSON
    """
    if not items:
        return ""
    if not isinstance(items, list):
        return str(items)

    out: List[str] = []
    for it in items:
        if it is None:
            continue
        if isinstance(it, str):
            s = it.strip()
            if s:
                out.append(f"• {s}")
            continue
        if isinstance(it, dict):
            if it.get("farmaco"):
                parts = [
                    it.get("farmaco"),
                    it.get("dosis"),
                    it.get("via"),
                    it.get("frecuencia"),
                ]
                s = " · ".join([str(p).strip() for p in parts if p])
                if s:
                    out.append(f"• {s}")
                continue
            for k in ("descripcion", "detalle", "resumen", "especialidad"):
                v = it.get(k)
                if isinstance(v, str) and v.strip():
                    out.append(f"• {v.strip()}")
                    break
            else:
                try:
                    out.append(f"• {json.dumps(it, ensure_ascii=False)}")
                except Exception:
                    out.append(f"• {str(it)}")
            continue
        out.append(f"• {str(it)}")

    return "\n".join(out).strip()


def _epc_pdf_payload_from_context(
    epc_doc: Dict[str, Any],
    patient: Optional[Patient],
    clinical: Dict[str, Any],
    hce: Optional[Dict[str, Any]] = None,  # <- NUEVO: pasar HCE para expandir labs
) -> Dict[str, Any]:
    """
    Arma el payload "amigable" para el PDF a partir del doc Mongo + paciente SQL + clinical derivado.
    """
    generated = epc_doc.get("generated") or {}
    gdata = generated.get("data") if isinstance(generated, dict) else None
    if not isinstance(gdata, dict):
        gdata = {}

    apellido = getattr(patient, "apellido", None) if patient else None
    nombre = getattr(patient, "nombre", None) if patient else None
    dni = getattr(patient, "dni", None) if patient else None
    sexo = getattr(patient, "sexo", None) if patient else None
    fn = getattr(patient, "fecha_nacimiento", None) if patient else None
    edad = _age_from_ymd(fn) if fn else None

    patient_full_name = ", ".join(
        [
            p
            for p in [
                str(apellido).strip() if apellido else "",
                str(nombre).strip() if nombre else "",
            ]
            if p
        ]
    ).strip()

    medico_name = (epc_doc.get("medico_responsable") or "").strip()

    fecha_emision = (
        epc_doc.get("fecha_emision") or epc_doc.get("updated_at") or epc_doc.get("created_at")
    )
    if isinstance(fecha_emision, str):
        dt = _parse_dt_maybe(fecha_emision)
        fecha_emision = dt or fecha_emision

    titulo = (epc_doc.get("titulo") or "Epicrisis de internación").strip()

    sections: Dict[str, Any] = {
        "Título": titulo,
    }

    if clinical:
        c_lines: List[str] = []
        if clinical.get("numero_historia_clinica"):
            c_lines.append(f"N° Historia Clínica: {clinical.get('numero_historia_clinica')}")
        if clinical.get("admision_num"):
            c_lines.append(f"N° Admisión: {clinical.get('admision_num')}")
        if clinical.get("protocolo"):
            c_lines.append(f"Protocolo: {clinical.get('protocolo')}")
        if clinical.get("fecha_ingreso_display") or clinical.get("fecha_ingreso"):
            c_lines.append(
                f"Fecha ingreso: {clinical.get('fecha_ingreso_display') or clinical.get('fecha_ingreso')}"
            )
        if clinical.get("fecha_egreso_display") or clinical.get("fecha_egreso"):
            c_lines.append(
                f"Fecha egreso: {clinical.get('fecha_egreso_display') or clinical.get('fecha_egreso')}"
            )
        if clinical.get("sector"):
            c_lines.append(f"Sector: {clinical.get('sector')}")
        if clinical.get("habitacion"):
            c_lines.append(f"Habitación: {clinical.get('habitacion')}")
        if clinical.get("cama"):
            c_lines.append(f"Cama: {clinical.get('cama')}")
        if c_lines:
            sections["Datos clínicos"] = "\n".join(c_lines)

    # IMPORTANTE:
    # El cliente pidió ELIMINAR del PDF cualquier impresión del diagnóstico CIE-10,
    # por lo que no agregamos una sección "Diagnóstico principal (CIE-10)".
    motivo = gdata.get("motivo_internacion") or generated.get("motivo_internacion") or ""
    evolucion = gdata.get("evolucion") or generated.get("evolucion") or ""

    if motivo:
        sections["Motivo de internación"] = str(motivo)
    if evolucion:
        sections["Evolución"] = str(evolucion)

    procedimientos = gdata.get("procedimientos") or generated.get("procedimientos") or []
    interconsultas = gdata.get("interconsultas") or generated.get("interconsultas") or []
    
    # Medicación - NUEVA ESTRUCTURA SEPARADA
    medicacion_internacion = gdata.get("medicacion_internacion") or generated.get("medicacion_internacion") or []
    medicacion_previa = gdata.get("medicacion_previa") or generated.get("medicacion_previa") or []
    medicacion_legacy = gdata.get("medicacion") or generated.get("medicacion") or []
    
    indicaciones_alta = gdata.get("indicaciones_alta") or generated.get("indicaciones_alta") or []
    recomendaciones = gdata.get("recomendaciones") or generated.get("recomendaciones") or []

    # EXPANSIÓN DE LABS PARA PDF
    # Leer configuración de exportación del usuario
    export_config = epc_doc.get("export_config", {})
    selected_labs = export_config.get("selected_labs", [])
    
    # Si procedimientos tiene el tag agrupado de labs, decidir qué hacer según selección
    if procedimientos and hce:
        procedimientos_expandidos = []
        labs_expandidos = False
        
        for proc_item in procedimientos:
            proc_str = str(proc_item) if not isinstance(proc_item, str) else proc_item
            
            # Detectar tag agrupado de labs
            if "Laboratorios realizados" in proc_str and "estudios)" in proc_str:
                # CASO 1: No hay selección → mantener tag agrupado
                if not selected_labs:
                    procedimientos_expandidos.append(proc_item)
                    continue
                
                # CASO 2: Hay selección → expandir solo los seleccionados
                parsed_hce = hce.get("ai_generated", {}) or {}
                parsed_data = parsed_hce.get("parsed_hce", {})
                procedimientos_hce = parsed_data.get("procedimientos", [])
                
                if procedimientos_hce:
                    # Filtrar solo laboratorios que estén en la selección del usuario
                    labs_individuales = [
                        p for p in procedimientos_hce 
                        if isinstance(p, dict) 
                        and p.get("categoria") == "laboratorio"
                        and p.get("descripcion") in selected_labs
                    ]
                    
                    if labs_individuales:
                        # Agregar header
                        procedimientos_expandidos.append("Laboratorios seleccionados:")
                        # Agregar cada lab con fecha y descripción
                        for lab in labs_individuales:
                            fecha = lab.get("fecha", "")[:16] if lab.get("fecha") else ""  # YYYY-MM-DD HH:MM
                            desc = lab.get("descripcion", "Lab")
                            if fecha:
                                procedimientos_expandidos.append(f"  {fecha}: {desc}")
                            else:
                                procedimientos_expandidos.append(f"  {desc}")
                        labs_expandidos = True
                    else:
                        # Selección sin labs válidos → mantener tag agrupado
                        procedimientos_expandidos.append(proc_item)
            
            # Si no es el tag agrupado, mantener como está
            if not ("Laboratorios realizados" in proc_str and "estudios)" in proc_str):
                procedimientos_expandidos.append(proc_item)
        
        # Si se expandió, usar la lista expandida
        if labs_expandidos:
            procedimientos = procedimientos_expandidos

    if procedimientos:
        sections["Procedimientos"] = _list_to_lines(procedimientos)
    if interconsultas:
        sections["Interconsultas"] = _list_to_lines(interconsultas)
    
    # MEDICACIÓN CON SUBSECCIONES
    # Si hay medicación separada (nueva estructura), mostrar con subsecciones
    # Si no, usar legacy para compatibilidad con EPCs antiguas
    if medicacion_internacion or medicacion_previa:
        med_lines = []
        
        if medicacion_internacion:
            med_lines.append("Medicación durante internación:")
            for med in medicacion_internacion:
                # Formatear: "FARMACO dosis via frecuencia"
                parts = [
                    med.get("farmaco", ""),
                    med.get("dosis", ""),
                    med.get("via", ""),
                    med.get("frecuencia", "")
                ]
                med_str = " ".join([p for p in parts if p]).strip()
                med_lines.append(f"• {med_str}")
        
        if medicacion_previa:
            if med_lines:  # Si ya hay medicación de internación, agregar espacio
                med_lines.append("")
            med_lines.append("Medicación habitual previa:")
            for med in medicacion_previa:
                parts = [
                    med.get("farmaco", ""),
                    med.get("dosis", ""),
                    med.get("via", "")
                ]
                med_str = " ".join([p for p in parts if p]).strip()
                med_lines.append(f"• {med_str}")
        
        if med_lines:
            sections["Plan Terapéutico"] = "\n".join(med_lines)
    elif medicacion_legacy:
        # Compatibilidad con EPCs antiguas
        sections["Plan Terapéutico"] = _list_to_lines(medicacion_legacy)
    
    if indicaciones_alta:
        sections["Indicaciones de alta"] = _list_to_lines(indicaciones_alta)
    if recomendaciones:
        sections["Recomendaciones"] = _list_to_lines(recomendaciones)

    clinic_name = (
        getattr(settings, "CLINIC_NAME", None)
        or getattr(settings, "APP_NAME", None)
        or "Clínica / Consultorio"
    )
    clinic_address = getattr(settings, "CLINIC_ADDRESS", None) or ""

    payload: Dict[str, Any] = {
        "id": epc_doc.get("_id"),
        "created_at": epc_doc.get("created_at"),
        "updated_at": epc_doc.get("updated_at"),
        "fecha_emision": fecha_emision,
        "clinic": {"name": clinic_name, "address": clinic_address},
        "patient": {
            "full_name": patient_full_name or (epc_doc.get("patient_id") or ""),
            "dni": dni or "",
            "age": edad if edad is not None else "",
            "sex": sexo or "",
        },
        "doctor": {
            "full_name": medico_name or "",
            "matricula": "",
        },
        "sections": sections,
    }
    return payload


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
        p_rows = (
            db.query(Patient)
            .filter(Patient.id == patient_id)
            .update({"estado": nuevo_estado}, synchronize_session=False)
        )

        a_rows = 0
        if admission_id:
            a_rows = (
                db.query(Admission)
                .filter(Admission.id == admission_id)
                .update({"estado": nuevo_estado}, synchronize_session=False)
            )

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
            "[%s] Error sincronizando estado SQL (patient_id=%s, admission_id=%s, estado=%s): %s",
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
    Lista HCE combinando:
    - pick_hce_collections()
    - colecciones cuyo nombre contenga 'hce' (case-insensitive)
      excluyendo 'epc_docs' y 'epc_versions'.
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
    colls = await _discover_hce_collections(limit=50)
    oid = _safe_objectid(hce_id)
    for c in colls:
        q = {"_id": oid} if oid else {"_id": hce_id}
        doc = await c.find_one(q)
        if doc:
            return doc
    return None


def _has_useful_hce_text(hce: Optional[Dict[str, Any]]) -> bool:
    if not hce:
        return False
    t = _extract_hce_text(hce) or ""
    min_chars = int(getattr(settings, "EPC_HCE_MIN_TEXT_CHARS", 80))
    return len(t.strip()) >= min_chars


async def _find_latest_hce_for_patient(
    patient_id: str,
    admission_id: Optional[str] = None,
    dni: Optional[str] = None,
    allow_any: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Busca HCE del paciente de forma robusta (string + UUID Binary subtype=4)
    y con campos alternativos típicos de integraciones.

    allow_any: ÚLTIMO fallback. Si está habilitado, solo toma HCE "sin asignar"
    para evitar agarrar HCE de otro paciente y generar EPC repetida.
    """
    colls = await _discover_hce_collections(limit=50)

    pvars = _uuid_variants(patient_id)
    avars = _uuid_variants(admission_id) if admission_id else []

    patient_or: List[Dict[str, Any]] = []
    for v in pvars:
        patient_or += [
            {"patient_id": v},
            {"patient.id": v},
            {"patientId": v},
            {"paciente_id": v},
            {"paciente.id": v},
        ]

    # 1) por patient_id + admisión
    if admission_id and avars:
        adm_or: List[Dict[str, Any]] = []
        for av in avars:
            adm_or += [
                {"admission_id": av},
                {"admission.id": av},
                {"admision_id": av},
                {"admision.id": av},
                {"admissionId": av},
            ]

        for c in colls:
            doc = await c.find_one(
                {"$and": [{"$or": patient_or}, {"$or": adm_or}]},
                sort=[("created_at", -1), ("_id", -1)],
            )
            if doc and _has_useful_hce_text(doc):
                return doc

    # 2) solo patient_id
    for c in colls:
        doc = await c.find_one(
            {"$or": patient_or},
            sort=[("created_at", -1), ("_id", -1)],
        )
        if doc and _has_useful_hce_text(doc):
            return doc

    # 3) por dni
    if dni:
        dni = str(dni).strip()
        if dni:
            dni_or = [{"dni": dni}, {"patient.dni": dni}, {"paciente.dni": dni}]
            for c in colls:
                doc = await c.find_one(
                    {"$or": dni_or},
                    sort=[("created_at", -1), ("_id", -1)],
                )
                if doc and _has_useful_hce_text(doc):
                    return doc

    # 4) fallback ANY (solo sin asignar) -> evita EPC repetida por HCE ajena
    if allow_any:
        unassigned = {
            "$or": [
                {"patient_id": {"$exists": False}},
                {"patient_id": ""},
                {"patient_id": None},
            ]
        }
        has_text = {
            "$or": [
                {"text": {"$exists": True, "$type": "string", "$ne": ""}},
                {"raw_text": {"$exists": True, "$type": "string", "$ne": ""}},
                {"content": {"$exists": True, "$type": "string", "$ne": ""}},
            ]
        }
        for c in colls:
            doc = await c.find_one(
                {"$and": [unassigned, has_text]},
                sort=[("created_at", -1), ("_id", -1)],
            )
            if doc and _has_useful_hce_text(doc):
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
        "estado": "borrador",
        "titulo": None,
        "diagnostico_principal_cie10": None,
        "fecha_emision": None,
        "medico_responsable": None,
        "firmado_por_medico": False,
        "created_by": str(getattr(user, "id", None)) if user else None,
        "created_by_name": _actor_name(user),  # ✅ Guardar nombre del usuario
        "created_at": _now(),
        "updated_at": _now(),
        "generated": None,
        "hce_origin_id": None,
    }
    await mongo.epc_docs.insert_one(doc)

    try:
        actor = _actor_name(user)
        log_epc_event(db, epc_id=_id, user_name=actor, action="EPC creada")
    except Exception as exc:
        log.warning("[open_epc_for_patient] No se pudo registrar evento EPC creada: %s", exc)

    return _epc_out(doc)


# -----------------------------------------------------------------------------
# FERRO D2 v3.0.0: Streaming EPC Generation (SSE)
# -----------------------------------------------------------------------------
@router.post(
    "/{epc_id}/stream",
    summary="Genera EPC con streaming SSE (FERRO D2)",
)
async def stream_epc_generation(
    epc_id: str,
    hce_id: Optional[str] = Query(default=None, description="HCE ID a usar"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    FERRO D2 v3.0.0: Streaming LLM endpoint.
    
    Returns Server-Sent Events (SSE) with chunks of generated content.
    Frontend can display partial results as they arrive.
    """
    from fastapi.responses import StreamingResponse
    import asyncio
    
    epc_doc = await mongo.epc_docs.find_one({"_id": epc_id})
    if not epc_doc:
        raise HTTPException(status_code=404, detail="EPC no encontrado")
    
    patient_id = epc_doc.get("patient_id")
    if not patient_id:
        raise HTTPException(status_code=400, detail="EPC sin patient_id")
    
    async def event_generator():
        """Generate SSE events with EPC content chunks."""
        try:
            # Send initial status
            yield f"data: {json.dumps({'status': 'started', 'message': 'Iniciando generación...'})}\n\n"
            
            # Find HCE
            if hce_id:
                hce = await _find_hce_by_id(hce_id)
            else:
                dni = None
                preg = PatientRepo(db).get(patient_id)
                if preg and getattr(preg, "dni", None):
                    dni = preg.dni
                hce = await _find_latest_hce_for_patient(
                    patient_id=patient_id,
                    admission_id=epc_doc.get("admission_id"),
                    dni=dni,
                    allow_any=False,
                )
            
            if not hce:
                yield f"data: {json.dumps({'status': 'error', 'message': 'HCE no encontrada'})}\n\n"
                return
            
            yield f"data: {json.dumps({'status': 'processing', 'message': 'HCE localizada, procesando...'})}\n\n"
            
            # Extract text
            hce_text = _extract_hce_text(hce)
            if not hce_text or len(hce_text.strip()) < 80:
                yield f"data: {json.dumps({'status': 'error', 'message': 'Texto HCE insuficiente'})}\n\n"
                return
            
            yield f"data: {json.dumps({'status': 'generating', 'message': 'Generando EPC con IA...'})}\n\n"
            
            # Generate using LangChain service
            from app.services.ai_langchain_service import LangChainAIService
            ai_service = LangChainAIService()
            
            result = await ai_service.generate_epc(hce_text=hce_text, pages=0)
            generated_data = result.get("json", {})
            
            # Stream sections progressively
            sections = [
                ("motivo_internacion", "Motivo de internación"),
                ("evolucion", "Evolución"),
                ("procedimientos", "Procedimientos"),
                ("interconsultas", "Interconsultas"),
                ("medicacion", "Medicación"),
                ("indicaciones_alta", "Indicaciones de alta"),
                ("recomendaciones", "Recomendaciones"),
            ]
            
            for key, label in sections:
                if generated_data.get(key):
                    yield f"data: {json.dumps({'status': 'section', 'section': key, 'label': label, 'content': generated_data[key]})}\n\n"
                    await asyncio.sleep(0.1)  # Small delay for progressive display
            
            # Save to MongoDB
            await mongo.epc_docs.update_one(
                {"_id": epc_id},
                {
                    "$set": {
                        "generated": {"data": generated_data, "provider": result.get("_provider")},
                        "hce_origin_id": str(hce.get("_id")),
                        "updated_at": _now(),
                    }
                },
            )
            
            yield f"data: {json.dumps({'status': 'completed', 'message': 'EPC generada exitosamente'})}\n\n"
            
        except Exception as e:
            log.error("[stream_epc] Error: %s", e)
            yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# -----------------------------------------------------------------------------
# Generar EPC desde IA (Gemini) usando HCE como fuente
# -----------------------------------------------------------------------------
@router.post(
    "/{epc_id}/generate",
    summary="Genera contenido de EPC usando IA y HCE",
)
async def generate_epc(
    epc_id: str,
    hce_id: Optional[str] = Query(default=None, description="Forzar la HCE a usar (_id de Mongo)"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
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
        if not _has_useful_hce_text(hce):
            raise HTTPException(status_code=422, detail="HCE encontrada pero sin texto clínico útil")
    else:
        dni = None
        preg = PatientRepo(db).get(patient_id)
        if preg and getattr(preg, "dni", None):
            dni = preg.dni

        allow_any = bool(getattr(settings, "EPC_FALLBACK_ANY_HCE", False))
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
                    "[1] patient_id+admission_id (string/Binary + campos alternativos), "
                    "[2] solo patient_id, [3] por DNI"
                    + (" y [4] fallback ANY (solo sin asignar) habilitado" if allow_any else "")
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
                await mongo.epc_docs.update_one({"_id": epc_id}, {"$set": {"admission_id": hce_adm}})
            except Exception as exc:
                log.warning(
                    "No se pudo actualizar admission_id en EPC (epc_id=%s, hce_admission_id=%s): %s",
                    epc_id,
                    hce_adm,
                    exc,
                )

    # ------------------------------------------------------------------
    # 1.c) Corregir patient_id según HCE (si viene completo y no coincide)
    # ------------------------------------------------------------------
    if hce:
        hce_patient_id = hce.get("patient_id")
        if hce_patient_id and hce_patient_id != patient_id:
            log.warning(
                "EPC %s tiene patient_id=%s pero HCE %s tiene patient_id=%s; se actualiza EPC para usar el de la HCE.",
                epc_id,
                patient_id,
                hce.get("_id"),
                hce_patient_id,
            )
            patient_id = hce_patient_id
            epc_doc["patient_id"] = patient_id
            try:
                await mongo.epc_docs.update_one({"_id": epc_id}, {"$set": {"patient_id": patient_id}})
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
    hce_text = _extract_hce_text(hce) if hce else ""
    hce_text = (hce_text or "").strip()
    min_chars = int(getattr(settings, "EPC_HCE_MIN_TEXT_CHARS", 80))

    if len(hce_text) < min_chars:
        raise HTTPException(
            status_code=422,
            detail=(
                "La HCE encontrada no contiene texto clínico útil para generar una EPC. "
                f"(len={len(hce_text)}, min={min_chars}). "
                "Esto evita que la IA 'invente' una epicrisis."
            ),
        )

    hce_sha = hashlib.sha256(hce_text.encode("utf-8", errors="ignore")).hexdigest()
    log.info(
        "[generate_epc] EPC=%s | HCE=%s | patient_id=%s | admission_id=%s | hce_sha=%s | text_len=%s",
        epc_id,
        str(hce.get("_id")) if hce else None,
        patient_id,
        admission_id,
        hce_sha,
        len(hce_text),
    )

    # ------------------------------------------------------------------
    # 2.b) Detectar tipo de HCE y usar parser apropiado
    # ------------------------------------------------------------------
    try:
        # Detectar si es HCE JSON estructurado (tiene ainstein.historia)
        is_json_hce = bool(
            hce and 
            isinstance(hce.get("ainstein"), dict) and 
            hce.get("ainstein", {}).get("historia")
        )
        
        if is_json_hce:
            # Usar parser JSON estructurado
            from app.services.hce_json_parser import generate_epc_from_json
            
            log.info("[generate_epc] Detectado HCE JSON estructurado, usando parser JSON")
            data = await generate_epc_from_json(hce, patient_id)
        else:
            # Usar parser de texto plano
            from app.services.epc_section_generator import generate_epc_by_sections
            
            log.info("[generate_epc] Usando generador por secciones (texto plano)")
            data = await generate_epc_by_sections(hce_text, patient_id)
        
        # Extraer campos del resultado
        motivo = data.get("motivo_internacion", "") or ""
        diag_cie10 = data.get("diagnostico_principal_cie10", "") or ""
        evolucion = data.get("evolucion", "") or ""
        procedimientos = data.get("procedimientos", []) or []
        interconsultas = data.get("interconsultas", []) or []
        medicacion = data.get("medicacion", []) or []
        indicaciones_alta = data.get("indicaciones_alta", []) or []
        notas_alta = data.get("notas_alta", []) or []
        
        # ⚠️ POST-PROCESAMIENTO: Detectar óbito desde tipo_alta del episodio
        try:
            from app.services.epc_pre_validator import EPCPreValidator
            from app.services.hce_ainstein_parser import HCEAinsteinParser
            
            # Parsear HCE para obtener tipo_alta
            parser = HCEAinsteinParser()
            parsed_hce = parser.parse_from_ainstein(hce)
            
            # Validar
            validator = EPCPreValidator()
            validation = validator.validate(parsed_hce)
            
            if validation.is_obito:
                log.info(f"[generate_epc] ⚠️ ÓBITO detectado: tipo_alta={validation.tipo_alta_oficial}")
                
                # Vaciar indicaciones si es óbito
                indicaciones_alta = []
                notas_alta = []
                
                # Post-procesar evolución para remover contradicciones
                from app.services.ai_langchain_service import _post_process_epc_result
                post_result = _post_process_epc_result({
                    "evolucion": evolucion,
                    "indicaciones_alta": indicaciones_alta,
                    "recomendaciones": notas_alta
                })
                evolucion = post_result.get("evolucion", evolucion)
                
                # Agregar marca de óbito a data
                data["_is_obito"] = True
                data["_tipo_alta"] = validation.tipo_alta_oficial
        except Exception as post_err:
            log.warning(f"[generate_epc] Error en post-procesamiento óbito: {post_err}")
        
        log.info(f"[generate_epc] Generación OK: meds={len(medicacion)}, procs={len(procedimientos)}")
        
    except Exception as section_err:
        log.warning(f"[generate_epc] Falló generador: {section_err}, usando fallback")
        import traceback
        traceback.print_exc()
        
        # Fallback al método anterior
        ai = GeminiAIService()
        prompt = f"""Analiza el siguiente texto de HCE y genera una EPICRISIS en JSON.
Campos: motivo_internacion, evolucion, procedimientos (lista), interconsultas (lista), 
medicacion (lista con tipo/farmaco/dosis/via/frecuencia), indicaciones_alta, notas_alta.
HCE: \"\"\"{hce_text[:12000]}\"\"\""""
        
        raw = await ai.generate_epc(prompt)
        data = _json_from_ai(raw) or {}
        
        motivo = data.get("motivo_internacion", "") or ""
        diag_cie10 = data.get("diagnostico_principal_cie10", "") or ""
        evolucion = data.get("evolucion", "") or ""
        procedimientos = data.get("procedimientos", []) or []
        interconsultas = data.get("interconsultas", []) or []
        medicacion = data.get("medicacion", []) or []
        indicaciones_alta = data.get("indicaciones_alta", []) or []
        notas_alta = data.get("notas_alta", []) or []

    # ------------------------------------------------------------------
    # 3) Normalizar interconsultas (compatibilidad)
    # ------------------------------------------------------------------
    ts = _now().isoformat() + "Z"
    
    # Convertir interconsultas a strings si son dicts
    interconsultas_detalle: List[Dict[str, Any]] = []
    if interconsultas and isinstance(interconsultas[0], dict):
        interconsultas_detalle = interconsultas
        interconsultas = [
            ic.get("especialidad") or ic.get("resumen") or str(ic) 
            for ic in interconsultas_detalle
        ]

    provider = "gemini"
    model = "gemini-2.0-flash"

    generated_doc = {
        "provider": provider,
        "model": model,
        "_provider": provider,
        "_model": model,
        "at": ts,
        "generated_at": ts,
        "hce_source_id": str(hce.get("_id")) if hce else None,
        "hce_text_sha256": hce_sha,
        "hce_text_len": len(hce_text),
        "motivo_internacion": motivo,
        "diagnostico_principal_cie10": diag_cie10,
        "evolucion": evolucion,
        "procedimientos": procedimientos,
        "interconsultas": interconsultas,
        "interconsultas_detalle": interconsultas_detalle,
        "medicacion": medicacion,
        "indicaciones_alta": indicaciones_alta,
        "notas_alta": notas_alta,
        "recomendaciones": notas_alta,  # Compatibilidad con frontend existente
        "data": data,
    }

    # ------------------------------------------------------------------
    # 4) Persistir en Mongo y sincronizar estados SQL
    # ------------------------------------------------------------------
    await mongo.epc_docs.update_one(
        {"_id": epc_id},
        {
            "$set": {
                "generated": generated_doc,
                "hce_origin_id": generated_doc["hce_source_id"],
                "diagnostico_principal_cie10": diag_cie10,
                "updated_at": _now(),
            }
        },
    )

    try:
        PatientRepo(db).upsert_status(
            patient_id=patient_id,
            estado=ESTADO_EPC_GENERADA,
            observaciones=(
                f"EPC generada (epc_id={epc_id}) a partir de HCE {generated_doc.get('hce_source_id')}"
            ),
        )
    except Exception as exc:
        log.warning(
            "[generate_epc] Error actualizando patient_status (patient_id=%s, epc_id=%s): %s",
            patient_id,
            epc_id,
            exc,
        )

    _sync_estado_sql(
        db=db,
        patient_id=patient_id,
        admission_id=admission_id,
        nuevo_estado=ESTADO_EPC_GENERADA,
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

    actor = _actor_name(user)
    try:
        log_epc_event(db, epc_id=epc_id, user_name=actor, action="EPC generada por IA")
    except Exception as exc:
        log.warning(
            "[generate_epc] No se pudo registrar evento en historial (epc_id=%s): %s",
            epc_id,
            exc,
        )

    return {"epc_id": epc_id, "version_id": version_doc["_id"], "status": "ok"}


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
                "provider": (d.get("generated") or {}).get("provider"),
                "model": (d.get("generated") or {}).get("model"),
            }
        )
    return {"items": items, "total": len(items)}


@router.get("/{epc_id}/versions/{version_id}")
async def get_epc_version(epc_id: str, version_id: str):
    doc = await mongo.epc_versions.find_one({"_id": version_id, "epc_id": epc_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Versión no encontrada")
    gen = doc.get("generated") or {}
    return {"id": str(doc.get("_id")), "epc_id": epc_id, "created_at": doc.get("created_at"), "source": doc.get("source"), "generated": gen}


# -----------------------------------------------------------------------------
# PDF: imprimir / descargar
# -----------------------------------------------------------------------------
@router.get(
    "/{epc_id}/pdf",
    summary="Descargar Epicrisis en PDF (attachment) o abrir (inline)",
)
async def get_epc_pdf(
    epc_id: str,
    download: bool = Query(default=True, description="Si true -> attachment, si false -> inline"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    epc_doc = await mongo.epc_docs.find_one({"_id": epc_id})
    if not epc_doc:
        raise HTTPException(status_code=404, detail="EPC no encontrado")

    patient_id = epc_doc.get("patient_id")
    patient = PatientRepo(db).get(patient_id) if patient_id else None

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
            allow_any=bool(getattr(settings, "EPC_FALLBACK_ANY_HCE", False)),
        )

    # Usar nueva función de extracción de datos clínicos (SOLID)
    clinical = _extract_clinical_data(hce) if hce else {}
    
    # Formatear fechas para display
    for key in ("fecha_ingreso", "fecha_egreso"):
        val = clinical.get(key)
        dt = _parse_dt_maybe(val)
        if dt:
            clinical[key + "_display"] = dt.strftime("%d/%m/%Y")

    payload = _epc_pdf_payload_from_context(epc_doc=epc_doc, patient=patient, clinical=clinical, hce=hce)
    pdf_bytes = build_epicrisis_pdf(payload)

    fname = f"epicrisis_{epc_id}.pdf"
    disposition = "attachment" if download else "inline"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="{fname}"'},
    )


@router.get(
    "/{epc_id}/print",
    summary="Abrir Epicrisis PDF para imprimir (inline)",
)
async def print_epc_pdf(
    epc_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await get_epc_pdf(epc_id=epc_id, download=False, db=db, user=user)


# -----------------------------------------------------------------------------
# Contexto de EPC: paciente + HCE asociada + médicos + historial
# -----------------------------------------------------------------------------
@router.get("/{epc_id}/context")
async def get_epc_context(
    epc_id: str,
    db: Session = Depends(get_db),
):
    epc_doc = await mongo.epc_docs.find_one({"_id": epc_id})
    if not epc_doc:
        raise HTTPException(status_code=404, detail="EPC no encontrado")

    patient_id = epc_doc.get("patient_id")
    patient = None
    if patient_id:
        patient = PatientRepo(db).get(patient_id)

    admission_out: Optional[Dict[str, Any]] = None
    admission_id = epc_doc.get("admission_id")
    try:
        adm_obj: Optional[Admission] = None
        if admission_id:
            adm_obj = db.query(Admission).filter(Admission.id == admission_id).first()
        if not adm_obj and patient_id:
            q = db.query(Admission).filter(Admission.patient_id == patient_id)
            if hasattr(Admission, "created_at"):
                q = q.order_by(getattr(Admission, "created_at").desc())
            elif hasattr(Admission, "fecha_ingreso"):
                q = q.order_by(getattr(Admission, "fecha_ingreso").desc())
            adm_obj = q.first()

        if adm_obj:
            admission_out = {
                "id": getattr(adm_obj, "id", None),
                "sector": getattr(adm_obj, "sector", None),
                "habitacion": getattr(adm_obj, "habitacion", None),
                "cama": getattr(adm_obj, "cama", None),
                "fecha_ingreso": getattr(adm_obj, "fecha_ingreso", None),
                "fecha_egreso": getattr(adm_obj, "fecha_egreso", None),
                "protocolo": getattr(adm_obj, "protocolo", None),
                "admision_num": getattr(adm_obj, "admision_num", None),
            }
    except Exception as exc:
        log.warning("[get_epc_context] No se pudo obtener admission SQL: %s", exc)
        admission_out = None

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
            allow_any=bool(getattr(settings, "EPC_FALLBACK_ANY_HCE", False)),
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
            "sexo": getattr(patient, "sexo", None),
            "fecha_nacimiento": getattr(patient, "fecha_nacimiento", None),
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

    demographics: Optional[Dict[str, Any]] = None
    if patient:
        sexo = getattr(patient, "sexo", None)
        fn = getattr(patient, "fecha_nacimiento", None)
        edad: Optional[int] = None
        if fn:
            try:
                y, m, d = fn.split("-")
                dob = date(int(y), int(m), int(d))
                today = date.today()
                edad = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            except Exception:
                edad = None
        demographics = {"sexo": sexo, "edad": edad}

    doctor_rows = (
        db.query(User)
        .join(Role, User.role_id == Role.id)
        .filter(Role.name == "medico", User.is_active.is_(True))
        .order_by(User.full_name)
        .all()
    )
    doctors = [{"id": str(u.id), "full_name": u.full_name, "username": u.username} for u in doctor_rows]

    history_rows = get_epc_history(db, epc_id)
    history = [{"at": ev.at.isoformat() if ev.at else None, "by": ev.by, "action": ev.action} for ev in history_rows]

    return {
        "epc": epc_out,
        "generated": generated,
        "patient": patient_out,
        "admission": admission_out,
        "hce": hce_out,
        "hce_text": hce_text,
        "clinical": clinical,
        "demographics": demographics,
        "doctors": doctors,
        "history": history,
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
        "fecha_emision",
        "medico_responsable",
        "firmado_por_medico",
        "estado",
        "generated",
        "diagnostico_principal_cie10",
    ]
    for f in allowed_fields:
        if f in payload:
            updates[f] = payload[f]

    if "estado" in updates and doc.get("patient_id"):
        patient_id = doc.get("patient_id")
        admission_id = doc.get("admission_id")
        nuevo_estado_epc = updates["estado"]

        if nuevo_estado_epc in ("validada", "impresa"):
            nuevo_estado_paciente = ESTADO_EPC_GENERADA
        else:
            nuevo_estado_paciente = ESTADO_INTERNACION

        try:
            PatientRepo(db).upsert_status(
                patient_id=patient_id,
                estado=nuevo_estado_paciente,
                observaciones=(
                    f"Estado EPC '{nuevo_estado_epc}' seteado por {getattr(user, 'username', 'sistema')}"
                ),
            )
        except Exception as exc:
            log.warning(
                "[update_epc] Error actualizando patient_status (patient_id=%s, epc_id=%s, estado_epc=%s): %s",
                patient_id,
                epc_id,
                nuevo_estado_epc,
                exc,
            )

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

    new_doc = await mongo.epc_docs.find_one({"_id": epc_id}) or doc

    actor = _actor_name(user)
    try:
        partes: List[str] = ["EPC actualizada"]
        if "estado" in updates:
            partes.append(f"(estado: {updates['estado']})")
        if "firmado_por_medico" in updates:
            partes.append("firmada por médico" if updates["firmado_por_medico"] else "sin firma")
        action = " ".join(partes)
        log_epc_event(db, epc_id=epc_id, user_name=actor, action=action)
    except Exception as exc:
        log.warning("[update_epc] No se pudo registrar evento en historial (epc_id=%s): %s", epc_id, exc)

    return _epc_out(new_doc)


# -----------------------------------------------------------------------------
# Feedback de secciones generadas por IA
# -----------------------------------------------------------------------------
class SectionFeedbackRequest(BaseModel):
    section: str  # motivo_internacion, evolucion, procedimientos, interconsultas, medicacion, indicaciones_alta, recomendaciones
    rating: str   # ok, partial, bad
    feedback_text: Optional[str] = None
    original_content: Optional[str] = None
    # Preguntas obligatorias para ratings negativos (partial/bad)
    has_omissions: Optional[bool] = None      # ¿Tiene omisiones?
    has_repetitions: Optional[bool] = None    # ¿Tiene repeticiones/excedentes?
    is_confusing: Optional[bool] = None       # ¿Es confuso o erróneo?


@router.post("/{epc_id}/feedback")
async def submit_section_feedback(
    epc_id: str,
    body: SectionFeedbackRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Guarda feedback de una sección generada por IA.
    - rating="ok" → No requiere feedback_text ni preguntas
    - rating="partial" o "bad" → Requiere feedback_text y las 3 preguntas SI/NO
    
    Preguntas obligatorias para ratings negativos:
    - has_omissions: ¿Tiene omisiones?
    - has_repetitions: ¿Tiene repeticiones/excedentes?
    - is_confusing: ¿Es confuso o erróneo?
    
    Este feedback se usa para mejorar el modelo de IA a futuro.
    """
    # Validar rating
    if body.rating not in ("ok", "partial", "bad"):
        raise HTTPException(status_code=400, detail="Rating inválido. Usar: ok, partial, bad")

    # Validar que feedback_text y las preguntas son obligatorias para ratings negativos
    if body.rating in ("partial", "bad"):
        if not (body.feedback_text or "").strip():
            raise HTTPException(
                status_code=400,
                detail="El feedback es obligatorio para calificaciones 'a medias' o 'mal'"
            )
        # Validar que las 3 preguntas están respondidas
        if body.has_omissions is None or body.has_repetitions is None or body.is_confusing is None:
            raise HTTPException(
                status_code=400,
                detail="Debe responder las 3 preguntas de evaluación (omisiones, repeticiones, confuso)"
            )

    # Validar EPC existe
    epc_doc = await mongo.epc_docs.find_one({"_id": epc_id})
    if not epc_doc:
        raise HTTPException(status_code=404, detail="EPC no encontrado")

    # Construir documento de feedback
    feedback_doc = {
        "epc_id": epc_id,
        "patient_id": epc_doc.get("patient_id"),
        "section": body.section,
        "rating": body.rating,
        "feedback_text": (body.feedback_text or "").strip() if body.feedback_text else None,
        "original_content": body.original_content,
        # Campos de preguntas (solo para ratings negativos)
        "has_omissions": body.has_omissions if body.rating in ("partial", "bad") else None,
        "has_repetitions": body.has_repetitions if body.rating in ("partial", "bad") else None,
        "is_confusing": body.is_confusing if body.rating in ("partial", "bad") else None,
        "created_by": str(getattr(user, "id", None)) if user else None,
        "created_by_name": _actor_name(user),
        "created_at": _now(),
    }

    # Insertar en colección epc_feedback
    await mongo.epc_feedback.insert_one(feedback_doc)

    log.info(
        "[submit_section_feedback] epc_id=%s section=%s rating=%s by=%s",
        epc_id,
        body.section,
        body.rating,
        _actor_name(user),
    )

    return {"ok": True, "message": "Feedback registrado correctamente"}


# -----------------------------------------------------------------------------
# Obtener feedback previo del usuario actual para una EPC
# -----------------------------------------------------------------------------
@router.get("/{epc_id}/my-feedback")
async def get_my_feedback(
    epc_id: str,
    user: User = Depends(get_current_user),
):
    """
    Retorna las evaluaciones previas del usuario actual para esta EPC.
    Permite que el evaluador vea lo que evaluó anteriormente.
    
    Returns:
        sections: diccionario con { section_name: { rating, feedback_text, created_at } }
        evaluated_at: fecha de la última evaluación
        has_previous: boolean indicando si hay evaluación previa
    """
    user_id = str(getattr(user, "id", None)) if user else None
    
    if not user_id:
        return {
            "has_previous": False,
            "sections": {},
            "evaluated_at": None,
        }
    
    # Buscar feedbacks del usuario para esta EPC
    cursor = mongo.epc_feedback.find({
        "epc_id": epc_id,
        "created_by": user_id,
    }).sort("created_at", -1)
    
    feedbacks = await cursor.to_list(100)
    
    if not feedbacks:
        return {
            "has_previous": False,
            "sections": {},
            "evaluated_at": None,
        }
    
    # Organizar por sección (usar la más reciente de cada sección)
    sections = {}
    latest_at = None
    
    for fb in feedbacks:
        section = fb.get("section")
        if section and section not in sections:
            created_at = fb.get("created_at")
            sections[section] = {
                "rating": fb.get("rating"),
                "feedback_text": fb.get("feedback_text"),
                "created_at": created_at.isoformat() if created_at else None,
            }
            if created_at and (latest_at is None or created_at > latest_at):
                latest_at = created_at
    
    return {
        "has_previous": True,
        "sections": sections,
        "evaluated_at": latest_at.isoformat() if latest_at else None,
        "evaluator_name": _actor_name(user),
    }


# -----------------------------------------------------------------------------
# Dashboard de estadísticas de feedback
# -----------------------------------------------------------------------------
@router.get("/feedback/stats")
async def get_feedback_stats(
    user: User = Depends(get_current_user),
):
    """
    Retorna estadísticas agregadas de feedback por sección y rating.
    Usado por el dashboard de administración para monitorear calidad de IA.
    """
    # Total por rating
    totals_cursor = mongo.epc_feedback.aggregate([
        {"$group": {"_id": "$rating", "count": {"$sum": 1}}}
    ])
    totals = await totals_cursor.to_list(None)

    # Por sección y rating
    by_section_cursor = mongo.epc_feedback.aggregate([
        {"$group": {
            "_id": {"section": "$section", "rating": "$rating"},
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id.section": 1, "_id.rating": 1}}
    ])
    by_section = await by_section_cursor.to_list(None)

    # Feedbacks recientes con texto (para mostrar en tabla)
    recent_cursor = mongo.epc_feedback.find(
        {"feedback_text": {"$ne": None, "$exists": True}},
        sort=[("created_at", -1)],
        limit=30
    )
    recent_raw = await recent_cursor.to_list(30)

    # Serializar para JSON (convertir ObjectId y datetime)
    recent_feedbacks = []
    for doc in recent_raw:
        recent_feedbacks.append({
            "id": str(doc.get("_id")),
            "epc_id": doc.get("epc_id"),
            "section": doc.get("section"),
            "rating": doc.get("rating"),
            "feedback_text": doc.get("feedback_text"),
            "created_by_name": doc.get("created_by_name"),
            "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
        })

    # Calcular totales
    total_count = sum(t.get("count", 0) for t in totals)
    ok_count = next((t.get("count", 0) for t in totals if t["_id"] == "ok"), 0)
    partial_count = next((t.get("count", 0) for t in totals if t["_id"] == "partial"), 0)
    bad_count = next((t.get("count", 0) for t in totals if t["_id"] == "bad"), 0)

    # Reestructurar by_section para frontend
    sections_data = {}
    for item in by_section:
        section = item["_id"]["section"]
        rating = item["_id"]["rating"]
        count = item["count"]
        if section not in sections_data:
            sections_data[section] = {"ok": 0, "partial": 0, "bad": 0, "total": 0}
        sections_data[section][rating] = count
        sections_data[section]["total"] += count

    # Generar insights automáticos mejorados
    # Primero obtener datos de preguntas para cada sección
    questions_for_insights_cursor = mongo.epc_feedback.aggregate([
        {"$match": {"rating": {"$in": ["partial", "bad"]}}},
        {"$group": {
            "_id": "$section",
            "has_omissions_true": {"$sum": {"$cond": [{"$eq": ["$has_omissions", True]}, 1, 0]}},
            "has_repetitions_true": {"$sum": {"$cond": [{"$eq": ["$has_repetitions", True]}, 1, 0]}},
            "is_confusing_true": {"$sum": {"$cond": [{"$eq": ["$is_confusing", True]}, 1, 0]}},
            "total": {"$sum": 1}
        }}
    ])
    questions_for_insights = await questions_for_insights_cursor.to_list(None)
    q_data = {item["_id"]: item for item in questions_for_insights}
    
    insights = []
    for section, data in sections_data.items():
        if data["total"] > 0:
            ok_pct = (data["ok"] / data["total"]) * 100
            bad_pct = (data["bad"] / data["total"]) * 100
            partial_pct = (data["partial"] / data["total"]) * 100
            negative_pct = bad_pct + partial_pct
            
            # Obtener problemas principales de esta sección
            section_q = q_data.get(section, {})
            omissions = section_q.get("has_omissions_true", 0)
            repetitions = section_q.get("has_repetitions_true", 0)
            confusing = section_q.get("is_confusing_true", 0)
            
            # Determinar problema principal
            problems = []
            if omissions > 0:
                problems.append(f"omisiones ({omissions})")
            if repetitions > 0:
                problems.append(f"repeticiones ({repetitions})")
            if confusing > 0:
                problems.append(f"confuso/erróneo ({confusing})")
            
            if negative_pct >= 50:
                main_problem = f"Principales problemas: {', '.join(problems)}." if problems else "Revisar generación."
                insights.append({
                    "type": "critical",
                    "section": section,
                    "message": f"⚠️ {section}: {negative_pct:.0f}% requiere mejora. {main_problem}"
                })
            elif bad_pct >= 20:
                main_problem = f"Detectado: {', '.join(problems)}." if problems else "Optimizar prompt."
                insights.append({
                    "type": "warning",
                    "section": section,
                    "message": f"📊 {section}: {ok_pct:.0f}% OK, {bad_pct:.0f}% negativo. {main_problem}"
                })
            elif ok_pct >= 90:
                insights.append({
                    "type": "success",
                    "section": section,
                    "message": f"✅ {section}: Excelente rendimiento ({ok_pct:.0f}% aprobación)."
                })
            elif ok_pct >= 70:
                insights.append({
                    "type": "info",
                    "section": section,
                    "message": f"📈 {section}: Rendimiento aceptable ({ok_pct:.0f}% OK). Margen de mejora: {negative_pct:.0f}%."
                })

    # Estadísticas de las 3 preguntas obligatorias
    questions_cursor = mongo.epc_feedback.aggregate([
        {"$match": {"rating": {"$in": ["partial", "bad"]}}},
        {"$group": {
            "_id": "$section",
            "has_omissions_true": {"$sum": {"$cond": [{"$eq": ["$has_omissions", True]}, 1, 0]}},
            "has_repetitions_true": {"$sum": {"$cond": [{"$eq": ["$has_repetitions", True]}, 1, 0]}},
            "is_confusing_true": {"$sum": {"$cond": [{"$eq": ["$is_confusing", True]}, 1, 0]}},
            "total_negative": {"$sum": 1}
        }}
    ])
    questions_raw = await questions_cursor.to_list(None)
    
    # Reestructurar para frontend
    questions_by_section = {}
    for item in questions_raw:
        section = item.get("_id")
        if section:
            questions_by_section[section] = {
                "omissions": item.get("has_omissions_true", 0),
                "repetitions": item.get("has_repetitions_true", 0),
                "confusing": item.get("is_confusing_true", 0),
                "total_negative": item.get("total_negative", 0),
            }
    
    # Totales de preguntas (para gráfico general)
    total_omissions = sum(q.get("omissions", 0) for q in questions_by_section.values())
    total_repetitions = sum(q.get("repetitions", 0) for q in questions_by_section.values())
    total_confusing = sum(q.get("confusing", 0) for q in questions_by_section.values())

    # =====================================================
    # Tendencias temporales - Comparación últimas 2 semanas
    # =====================================================
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    one_week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)
    
    # Semana actual (últimos 7 días)
    current_week_cursor = mongo.epc_feedback.aggregate([
        {"$match": {"created_at": {"$gte": one_week_ago}}},
        {"$group": {
            "_id": "$section",
            "ok": {"$sum": {"$cond": [{"$eq": ["$rating", "ok"]}, 1, 0]}},
            "negative": {"$sum": {"$cond": [{"$in": ["$rating", ["partial", "bad"]]}, 1, 0]}},
            "total": {"$sum": 1}
        }}
    ])
    current_week_raw = await current_week_cursor.to_list(None)
    current_week = {item["_id"]: item for item in current_week_raw}
    
    # Semana anterior (7-14 días atrás)
    prev_week_cursor = mongo.epc_feedback.aggregate([
        {"$match": {"created_at": {"$gte": two_weeks_ago, "$lt": one_week_ago}}},
        {"$group": {
            "_id": "$section",
            "ok": {"$sum": {"$cond": [{"$eq": ["$rating", "ok"]}, 1, 0]}},
            "negative": {"$sum": {"$cond": [{"$in": ["$rating", ["partial", "bad"]]}, 1, 0]}},
            "total": {"$sum": 1}
        }}
    ])
    prev_week_raw = await prev_week_cursor.to_list(None)
    prev_week = {item["_id"]: item for item in prev_week_raw}
    
    # Calcular tendencias por sección
    trends = []
    all_sections = set(current_week.keys()) | set(prev_week.keys())
    for section in all_sections:
        curr = current_week.get(section, {"ok": 0, "negative": 0, "total": 0})
        prev = prev_week.get(section, {"ok": 0, "negative": 0, "total": 0})
        
        curr_ok_pct = (curr["ok"] / curr["total"] * 100) if curr["total"] > 0 else 0
        prev_ok_pct = (prev["ok"] / prev["total"] * 100) if prev["total"] > 0 else 0
        change = curr_ok_pct - prev_ok_pct
        
        if curr["total"] >= 3 or prev["total"] >= 3:  # Solo si hay datos significativos
            trends.append({
                "section": section,
                "current_ok_pct": round(curr_ok_pct, 1),
                "previous_ok_pct": round(prev_ok_pct, 1),
                "change_pct": round(change, 1),
                "status": "improving" if change > 5 else ("declining" if change < -5 else "stable"),
                "current_total": curr["total"],
                "previous_total": prev["total"],
            })
    
    # Ordenar por cambio (peores primero para priorizar)
    trends.sort(key=lambda x: x["change_pct"])
    
    # Resumen global de tendencia
    total_curr = sum(current_week.get(s, {}).get("total", 0) for s in all_sections)
    total_prev = sum(prev_week.get(s, {}).get("total", 0) for s in all_sections)
    ok_curr = sum(current_week.get(s, {}).get("ok", 0) for s in all_sections)
    ok_prev = sum(prev_week.get(s, {}).get("ok", 0) for s in all_sections)
    
    global_curr_pct = (ok_curr / total_curr * 100) if total_curr > 0 else 0
    global_prev_pct = (ok_prev / total_prev * 100) if total_prev > 0 else 0
    global_change = global_curr_pct - global_prev_pct

    return {
        "summary": {
            "total": total_count,
            "ok": ok_count,
            "partial": partial_count,
            "bad": bad_count,
            "ok_pct": round((ok_count / total_count * 100) if total_count > 0 else 0, 1),
            "partial_pct": round((partial_count / total_count * 100) if total_count > 0 else 0, 1),
            "bad_pct": round((bad_count / total_count * 100) if total_count > 0 else 0, 1),
        },
        "by_section": sections_data,
        "questions_summary": {
            "omissions": total_omissions,
            "repetitions": total_repetitions,
            "confusing": total_confusing,
        },
        "questions_by_section": questions_by_section,
        "recent_feedbacks": recent_feedbacks,
        "insights": insights,
        "trends": {
            "global_current_pct": round(global_curr_pct, 1),
            "global_previous_pct": round(global_prev_pct, 1),
            "global_change_pct": round(global_change, 1),
            "global_status": "improving" if global_change > 3 else ("declining" if global_change < -3 else "stable"),
            "by_section": trends,
            "current_week_total": total_curr,
            "previous_week_total": total_prev,
        },
    }


# -----------------------------------------------------------------------------
# Insights de Aprendizaje Continuo por Sección (con análisis LLM)
# -----------------------------------------------------------------------------
@router.get("/feedback/insights")
async def get_feedback_insights(
    force_refresh: bool = False,
    user: User = Depends(get_current_user),
):
    """
    Retorna insights de aprendizaje continuo extraídos del feedback.
    Usa LLM (Gemini) para analizar comentarios y generar insights profesionales.
    
    Args:
        force_refresh: Si True, recalcula los insights ignorando el caché
    
    Returns:
        Diccionario con análisis por sección, problemas categorizados, y reglas
    """
    from app.services.feedback_llm_analyzer import get_feedback_llm_analyzer
    
    analyzer = get_feedback_llm_analyzer()
    analysis = await analyzer.analyze_all_sections(force_refresh=force_refresh)
    
    return {
        "sections": analysis.get("sections", []),
        "total_feedbacks_analyzed": analysis.get("total_feedbacks_analyzed", 0),
        "computed_at": analysis.get("computed_at"),
        "cache_info": {
            "cached": not force_refresh,
            "ttl_hours": 24,
        }
    }


# -----------------------------------------------------------------------------
# Estadísticas del Sistema de Aprendizaje Continuo
# -----------------------------------------------------------------------------
@router.get("/feedback/learning-stats")
async def get_learning_stats(
    user: User = Depends(get_current_user),
):
    """
    Retorna estadísticas del sistema de aprendizaje continuo:
    - Cantidad de análisis ejecutados
    - Problemas detectados y reglas generadas
    - Evolución temporal
    """
    from datetime import datetime, timedelta
    
    now = datetime.utcnow()
    one_week_ago = now - timedelta(days=7)
    one_month_ago = now - timedelta(days=30)
    
    # Total de eventos de aprendizaje
    total_events = await mongo.learning_events.count_documents({})
    
    # Eventos última semana vs mes anterior
    events_this_week = await mongo.learning_events.count_documents(
        {"timestamp": {"$gte": one_week_ago}}
    )
    events_last_month = await mongo.learning_events.count_documents(
        {"timestamp": {"$gte": one_month_ago}}
    )
    
    # Último análisis
    last_event = await mongo.learning_events.find_one(
        sort=[("timestamp", -1)]
    )
    
    # Agregar estadísticas acumuladas
    pipeline = [
        {"$group": {
            "_id": None,
            "total_feedbacks": {"$sum": "$feedbacks_analyzed"},
            "total_problems": {"$sum": "$total_problems_found"},
            "total_rules": {"$sum": "$total_rules_generated"},
            "avg_feedbacks_per_analysis": {"$avg": "$feedbacks_analyzed"},
            "avg_problems_per_analysis": {"$avg": "$total_problems_found"},
        }}
    ]
    agg_cursor = mongo.learning_events.aggregate(pipeline)
    agg_result = await agg_cursor.to_list(1)
    totals = agg_result[0] if agg_result else {}
    
    # Historial por semana (últimas 4 semanas)
    weekly_pipeline = [
        {"$match": {"timestamp": {"$gte": one_month_ago}}},
        {"$group": {
            "_id": {
                "week": {"$week": "$timestamp"},
                "year": {"$year": "$timestamp"}
            },
            "events": {"$sum": 1},
            "problems": {"$sum": "$total_problems_found"},
            "rules": {"$sum": "$total_rules_generated"},
        }},
        {"$sort": {"_id.year": 1, "_id.week": 1}}
    ]
    weekly_cursor = mongo.learning_events.aggregate(weekly_pipeline)
    weekly_data = await weekly_cursor.to_list(10)
    
    return {
        "summary": {
            "total_analyses": total_events,
            "analyses_this_week": events_this_week,
            "analyses_this_month": events_last_month,
            "total_feedbacks_processed": totals.get("total_feedbacks", 0),
            "total_problems_detected": totals.get("total_problems", 0),
            "total_rules_generated": totals.get("total_rules", 0),
            "avg_feedbacks_per_analysis": round(totals.get("avg_feedbacks_per_analysis", 0), 1),
            "avg_problems_per_analysis": round(totals.get("avg_problems_per_analysis", 0), 1),
        },
        "last_analysis": {
            "timestamp": last_event.get("timestamp").isoformat() if last_event and last_event.get("timestamp") else None,
            "feedbacks_analyzed": last_event.get("feedbacks_analyzed") if last_event else 0,
            "problems_found": last_event.get("total_problems_found") if last_event else 0,
            "rules_generated": last_event.get("total_rules_generated") if last_event else 0,
        } if last_event else None,
        "weekly_history": [
            {
                "week": f"S{item['_id']['week']}",
                "events": item.get("events", 0),
                "problems": item.get("problems", 0),
                "rules": item.get("rules", 0),
            }
            for item in weekly_data
        ],
    }


# -----------------------------------------------------------------------------
# Feedbacks agrupados por EPC → Evaluador
# -----------------------------------------------------------------------------
@router.get("/feedback/grouped")
async def get_feedback_grouped(
    user: User = Depends(get_current_user),
):
    """
    Retorna feedbacks agrupados por EPC → Evaluador (por sesión) → Secciones.
    Incluye datos del paciente y HCE origen para cada EPC.
    
    Una sesión de evaluación son exactamente 7 secciones (una evaluación completa).
    Si el mismo evaluador evaluó la misma EPC múltiples veces, cada grupo de 7
    se muestra como una sesión separada con su propia fecha/hora.
    """
    from app.repositories.patient_repo import PatientRepo
    from sqlalchemy.orm import Session
    from app.core.deps import get_db
    
    # Máximo de secciones por sesión de evaluación
    MAX_SECTIONS_PER_SESSION = 7
    
    # Obtener todos los feedbacks ordenados por fecha (más recientes primero)
    cursor = mongo.epc_feedback.find({}).sort("created_at", -1)
    all_feedbacks = await cursor.to_list(500)  # Limitar a 500 feedbacks
    
    if not all_feedbacks:
        return {"grouped_epc": []}
    
    # Ordenar por EPC, evaluador, y fecha para agrupar correctamente
    # Primero por EPC, luego por evaluador, luego por fecha ASC para crear sesiones en orden
    all_feedbacks.sort(key=lambda x: (
        x.get("epc_id") or "",
        x.get("created_by") or "",
        x.get("created_at") or datetime.min
    ))
    
    # Organizar feedbacks por epc_id → evaluador → sesiones (bloques de 7)
    epc_map: Dict[str, Dict[str, Any]] = {}
    
    # Track de sesiones por evaluador
    evaluator_session_counts: Dict[str, int] = {}  # key: "epc_evaluator" -> count
    
    for fb in all_feedbacks:
        epc_id = fb.get("epc_id")
        if not epc_id:
            continue
            
        if epc_id not in epc_map:
            epc_map[epc_id] = {
                "epc_id": epc_id,
                "patient_id": fb.get("patient_id"),
                "evaluators": {},
            }
        
        evaluator_name = fb.get("created_by_name") or "Anónimo"
        evaluator_id = fb.get("created_by") or "unknown"
        fb_created_at = fb.get("created_at")
        
        # Key base para este evaluador en esta EPC
        base_key = f"{epc_id}_{evaluator_id}_{evaluator_name}"
        
        # Buscar sesión existente que tenga menos de 7 secciones
        session_key = None
        for existing_key, existing_session in epc_map[epc_id]["evaluators"].items():
            if existing_key.startswith(f"{evaluator_id}_{evaluator_name}_"):
                if len(existing_session["sections"]) < MAX_SECTIONS_PER_SESSION:
                    session_key = existing_key
                    break
        
        # Si no hay sesión con espacio, crear una nueva
        if session_key is None:
            session_num = evaluator_session_counts.get(base_key, 0) + 1
            evaluator_session_counts[base_key] = session_num
            session_key = f"{evaluator_id}_{evaluator_name}_{session_num}"
            epc_map[epc_id]["evaluators"][session_key] = {
                "evaluator_id": evaluator_id,
                "evaluator_name": evaluator_name,
                "evaluated_at": fb_created_at.isoformat() if fb_created_at else None,
                "sections": [],
            }
        
        epc_map[epc_id]["evaluators"][session_key]["sections"].append({
            "section": fb.get("section"),
            "rating": fb.get("rating"),
            "feedback_text": fb.get("feedback_text"),
            "created_at": fb_created_at.isoformat() if fb_created_at else None,
            # Campos de preguntas obligatorias
            "has_omissions": fb.get("has_omissions"),
            "has_repetitions": fb.get("has_repetitions"),
            "is_confusing": fb.get("is_confusing"),
        })
    
    # Enriquecer con datos del EPC (paciente, HCE origen)
    epc_ids = list(epc_map.keys())
    epc_docs_cursor = mongo.epc_docs.find({"_id": {"$in": epc_ids}})
    epc_docs_list = await epc_docs_cursor.to_list(len(epc_ids))
    epc_docs_map = {doc["_id"]: doc for doc in epc_docs_list}
    
    # Obtener patient_ids para buscar nombres
    patient_ids = set()
    for epc_data in epc_map.values():
        if epc_data.get("patient_id"):
            patient_ids.add(epc_data["patient_id"])
    
    # Para cada EPC, buscar el nombre del paciente desde epc_docs
    grouped_result = []
    for epc_id, epc_data in epc_map.items():
        epc_doc = epc_docs_map.get(epc_id, {})
        patient_id = epc_data.get("patient_id") or epc_doc.get("patient_id")
        
        # Buscar nombre del paciente desde SQL si está disponible
        patient_name = None
        if patient_id:
            # Intentar obtener de epc_created_by_name si existe, o construir desde otra fuente
            # Por ahora usamos el patient_id como fallback
            patient_name = patient_id
        
        hce_origin_id = None
        if epc_doc:
            gen = epc_doc.get("generated") or {}
            hce_origin_id = gen.get("hce_source_id") or epc_doc.get("hce_origin_id")
        
        epc_created_at = epc_doc.get("created_at")
        if epc_created_at:
            epc_created_at = epc_created_at.isoformat() if hasattr(epc_created_at, "isoformat") else str(epc_created_at)
        
        # Convertir evaluators dict a lista y limpiar campos internos
        evaluators_list = []
        for session in epc_data["evaluators"].values():
            clean_session = {k: v for k, v in session.items() if not k.startswith("_")}
            evaluators_list.append(clean_session)
        
        grouped_result.append({
            "epc_id": epc_id,
            "patient_id": patient_id,
            "patient_name": patient_name,
            "hce_origin_id": hce_origin_id,
            "epc_created_at": epc_created_at,
            "evaluators": evaluators_list,
            "total_sections_evaluated": sum(len(e["sections"]) for e in evaluators_list),
        })
    
    # Ordenar por cantidad de secciones evaluadas (más evaluadas primero)
    grouped_result.sort(key=lambda x: x["total_sections_evaluated"], reverse=True)
    
    return {"grouped_epc": grouped_result}


# -----------------------------------------------------------------------------
# Eliminar feedbacks de un evaluador específico
# -----------------------------------------------------------------------------
@router.delete("/feedback/{epc_id}/evaluator/{evaluator_id}")
async def delete_evaluator_feedback(
    epc_id: str,
    evaluator_id: str,
    user: User = Depends(get_current_user),
):
    """
    Elimina todos los feedbacks de un evaluador específico para una EPC.
    Útil para limpiar evaluaciones de prueba.
    """
    # Buscar y eliminar feedbacks que coincidan con epc_id y created_by
    result = await mongo.epc_feedback.delete_many({
        "epc_id": epc_id,
        "created_by": evaluator_id,
    })
    
    deleted_count = result.deleted_count
    
    log.info(
        "[delete_evaluator_feedback] epc_id=%s evaluator_id=%s deleted=%d by=%s",
        epc_id,
        evaluator_id,
        deleted_count,
        _actor_name(user),
    )
    
    return {
        "ok": True,
        "deleted_count": deleted_count,
        "message": f"Se eliminaron {deleted_count} feedbacks del evaluador.",
    }


# -----------------------------------------------------------------------------
# Costos de LLM - Dashboard de administración
# -----------------------------------------------------------------------------
@router.get("/admin/llm-costs")
async def get_llm_costs(
    from_date: Optional[str] = Query(None, description="Fecha inicio (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="Fecha fin (YYYY-MM-DD)"),
    user: User = Depends(get_current_user),
):
    """
    Retorna estadísticas de uso y costos de LLM.
    
    Muestra:
    - EPCs generadas por día
    - Procesos de aprendizaje continuo ejecutados
    - Tokens utilizados (input + output)
    - Costo estimado en USD
    
    Args:
        from_date: Fecha inicio (YYYY-MM-DD), default: últimos 30 días
        to_date: Fecha fin (YYYY-MM-DD), default: hoy
    
    Returns:
        daily: Lista de estadísticas por día
        summary: Resumen del período
        models: Desglose por modelo
    """
    from app.services.llm_usage_tracker import get_llm_usage_tracker
    from datetime import timedelta
    
    tracker = get_llm_usage_tracker()
    
    # Costo de transacción por operación (fijo)
    TRANSACTION_COST_PER_EPC = 0.0055
    TRANSACTION_COST_PER_LEARNING = 0.0055  # Mismo costo que EPC
    
    # Defaults: últimos 30 días
    if not to_date:
        to_date = datetime.utcnow().strftime("%Y-%m-%d")
    if not from_date:
        from_dt = datetime.utcnow() - timedelta(days=30)
        from_date = from_dt.strftime("%Y-%m-%d")
    
    # Obtener datos
    daily = await tracker.get_daily_stats(from_date, to_date)
    summary = await tracker.get_summary(from_date, to_date)
    models = await tracker.get_model_breakdown(from_date, to_date)
    
    # Calcular costo de transacción total (EPC + Learning)
    epc_transaction_cost = summary.get("total_epcs", 0) * TRANSACTION_COST_PER_EPC
    learning_transaction_cost = summary.get("total_learning", 0) * TRANSACTION_COST_PER_LEARNING
    total_transaction_cost = epc_transaction_cost + learning_transaction_cost
    
    # Agregar costo de transacción a cada día
    for day_data in daily:
        epc_count = day_data.get("epc_count", 0)
        learning_count = day_data.get("learning_count", 0)
        day_data["epc_transaction_cost_usd"] = epc_count * TRANSACTION_COST_PER_EPC
        day_data["learning_transaction_cost_usd"] = learning_count * TRANSACTION_COST_PER_LEARNING
        day_data["transaction_cost_usd"] = day_data["epc_transaction_cost_usd"] + day_data["learning_transaction_cost_usd"]
        day_data["total_cost_usd"] = round(day_data.get("cost_usd", 0) + day_data["transaction_cost_usd"], 4)
    
    # Agregar costo de transacción al summary
    summary["epc_transaction_cost_usd"] = round(epc_transaction_cost, 4)
    summary["learning_transaction_cost_usd"] = round(learning_transaction_cost, 4)
    summary["transaction_cost_usd"] = round(total_transaction_cost, 4)
    summary["llm_cost_usd"] = summary.get("total_cost_usd", 0)
    summary["total_cost_usd"] = round(summary.get("total_cost_usd", 0) + total_transaction_cost, 4)
    
    return {
        "from_date": from_date,
        "to_date": to_date,
        "daily": daily,
        "summary": summary,
        "models": models,
        "pricing_info": {
            "note": "Costos estimados basados en pricing de Gemini + costo de transacción",
            "transaction_cost_per_epc": TRANSACTION_COST_PER_EPC,
            "gemini-2.0-flash": {
                "input_per_1m": 0.075,
                "output_per_1m": 0.30,
            }
        }
    }