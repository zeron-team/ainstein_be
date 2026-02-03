# app/services/epc/hce_extractor.py
"""
Servicio de extracción de texto de HCE.

Responsabilidad única: Extraer texto clínico de diferentes fuentes de HCE.

Soporta:
- HCE de Ainstein (WebService)
- HCE de PDF
- HCE genéricas
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from bson import ObjectId, Binary
from uuid import UUID

log = logging.getLogger(__name__)


class HCEExtractor:
    """
    Extractor de texto de HCE.
    
    Uso:
        extractor = HCEExtractor()
        text = extractor.extract(hce_doc)
    """
    
    def extract(self, hce_doc: Dict[str, Any]) -> str:
        """
        Extrae texto clínico de un documento HCE.
        Detecta automáticamente el tipo de HCE.
        """
        if not hce_doc:
            return ""
        
        # HCE de Ainstein
        if "ainstein" in hce_doc:
            return self._extract_ainstein(hce_doc)
        
        # HCE genérica
        return self._pick_best_text(hce_doc)
    
    def _extract_ainstein(self, hce_doc: Dict[str, Any]) -> str:
        """Extrae texto de HCE importadas desde Ainstein."""
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
            
            # Medicación
            medicacion = entrada.get("indicacionFarmacologica") or []
            if medicacion:
                med_texts = self._extract_medications(medicacion)
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
            
            # Plantillas
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
                        clean_val = val.replace("<br>", " ").replace("<br/>", " ")
                        clean_val = " ".join(clean_val.split())
                        label = prop.get("grprDescripcion", "Campo")
                        pl_values.append(f"{label}: {clean_val}")
                if pl_values:
                    if grupo:
                        entry_parts.append(f"[{grupo}]")
                    entry_parts.extend(pl_values)
            
            if len(entry_parts) > 1:
                parts.extend(entry_parts)
        
        return "\n".join(parts).strip()
    
    def extract_clinical_data(self, hce_doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extrae datos clínicos estructurados de la HCE.
        Soporta tanto HCE structured como Ainstein.
        
        Returns:
            Dict con claves: fecha_ingreso, fecha_egreso, sector, habitacion,
            cama, numero_historia_clinica, admision_num, protocolo, tipo_alta
        """
        clinical: Dict[str, Any] = {}
        
        if not hce_doc:
            return clinical
        
        # Prioridad 1: Datos de Ainstein episodio
        ainstein = hce_doc.get("ainstein") or {}
        episodio = ainstein.get("episodio") or {}
        
        if episodio:
            clinical["fecha_ingreso"] = episodio.get("inteFechaIngreso")
            clinical["fecha_egreso"] = episodio.get("inteFechaEgreso")
            clinical["tipo_alta"] = episodio.get("taltDescripcion")
            clinical["dias_estada"] = episodio.get("inteDiasEstada")
            clinical["numero_historia_clinica"] = episodio.get("paciNroHisto") or episodio.get("paciNroDoc")
            clinical["admision_num"] = episodio.get("inteNumero")
            clinical["sector"] = episodio.get("servDescripcion") or episodio.get("salaDescripcion")
            clinical["habitacion"] = episodio.get("habiNumero")
            clinical["cama"] = episodio.get("camaDescripcion")
            clinical["paciente_edad"] = episodio.get("paciEdad")
            clinical["paciente_sexo"] = episodio.get("paciSexo")
        
        # Prioridad 2: Fallback a structured
        structured = hce_doc.get("structured") or {}
        
        # Solo llenar campos que no se obtuvieron de Ainstein
        mappings = [
            ("fecha_ingreso", ["fecha_ingreso", "fecha_admision", "ingreso_fecha", "Fecha Ingreso"]),
            ("fecha_egreso", ["fecha_egreso", "fecha_alta", "egreso_fecha", "Fecha Egreso"]),
            ("sector", ["sector", "servicio", "unidad", "sector_internacion", "Sector"]),
            ("habitacion", ["habitacion", "hab", "habitacion_num", "nro_habitacion"]),
            ("cama", ["cama", "cama_num", "nro_cama"]),
            ("numero_historia_clinica", ["numero_historia_clinica", "nro_hc", "hc_numero", "historia_clinica"]),
            ("admision_num", ["admision_num", "admission_num", "numero_admision", "nro_admision"]),
            ("protocolo", ["protocolo", "protocolo_num", "numero_protocolo"]),
        ]
        
        for target_key, source_keys in mappings:
            if not clinical.get(target_key):
                for src in source_keys:
                    val = structured.get(src)
                    if val:
                        clinical[target_key] = val
                        break
        
        # Limpiar valores None
        return {k: v for k, v in clinical.items() if v is not None}
    
    def _extract_medications(self, medicacion: List[Dict]) -> List[str]:
        """Extrae texto de medicación."""
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
        return med_texts
    
    def _pick_best_text(self, doc: Dict[str, Any]) -> str:
        """
        Priorizamos texto de HCE:
        1) text
        2) structured["texto_completo"] / ["texto"] / ["descripcion"]
        3) raw_text
        4) content / body / contenido (por integraciones WS)
        """
        # Opción 1: campo text directo
        txt = doc.get("text")
        if txt and isinstance(txt, str) and len(txt.strip()) > 50:
            return txt.strip()
        
        # Opción 2: structured
        structured = doc.get("structured") or {}
        for key in ("texto_completo", "texto", "descripcion", "contenido"):
            val = structured.get(key)
            if val and isinstance(val, str) and len(val.strip()) > 50:
                return val.strip()
        
        # Opción 3: raw_text
        raw = doc.get("raw_text")
        if raw and isinstance(raw, str) and len(raw.strip()) > 50:
            return raw.strip()
        
        # Opción 4: campos de integración WS
        for key in ("content", "body", "contenido", "texto"):
            val = doc.get(key)
            if val and isinstance(val, str) and len(val.strip()) > 50:
                return val.strip()
        
        return ""


# Función de conveniencia para extraer datos clínicos
def extract_clinical_data(hce_doc: Dict[str, Any]) -> Dict[str, Any]:
    """Extrae datos clínicos estructurados de HCE."""
    extractor = HCEExtractor()
    return extractor.extract_clinical_data(hce_doc)# ============================================================================
# Funciones de conveniencia (para compatibilidad con router)
# ============================================================================

def extract_hce_text(hce_doc: Dict[str, Any]) -> str:
    """Extrae texto de HCE (función de conveniencia)."""
    extractor = HCEExtractor()
    return extractor.extract(hce_doc)


async def find_hce_by_id(hce_id: str):
    """Busca HCE por ID en MongoDB."""
    from app.adapters.mongo_client import db as mongo
    from .helpers import safe_objectid
    
    oid = safe_objectid(hce_id)
    if not oid:
        return None
    
    # Buscar en colecciones de HCE
    for coll_name in ["hce_docs", "hce_clinical"]:
        try:
            coll = mongo[coll_name]
            doc = await coll.find_one({"_id": oid})
            if doc:
                return doc
        except Exception as e:
            log.warning(f"[HCE] Error buscando en {coll_name}: {e}")
    
    return None


async def find_latest_hce_for_patient(
    patient_id: str,
    admission_id: Optional[str] = None,
    dni: Optional[str] = None,
):
    """
    Busca HCE más reciente del paciente.
    Soporta múltiples formatos de ID.
    """
    from app.adapters.mongo_client import db as mongo
    from .helpers import uuid_variants
    
    # Construir query
    or_conditions = []
    
    # Por patient_id (string y Binary)
    for variant in uuid_variants(patient_id):
        or_conditions.append({"patient_id": variant})
    
    # Por admission_id si existe
    if admission_id:
        for variant in uuid_variants(admission_id):
            or_conditions.append({"admission_id": variant})
    
    # Por DNI si existe
    if dni:
        or_conditions.append({"structured.dni": dni})
        or_conditions.append({"ainstein.episodio.paciNroDoc": dni})
    
    if not or_conditions:
        return None
    
    query = {"$or": or_conditions}
    
    # Buscar en colecciones
    for coll_name in ["hce_docs", "hce_clinical"]:
        try:
            coll = mongo[coll_name]
            doc = await coll.find_one(
                query,
                sort=[("created_at", -1)]
            )
            if doc:
                return doc
        except Exception as e:
            log.warning(f"[HCE] Error buscando en {coll_name}: {e}")
    
    return None
