# app/services/epc/pdf_builder.py
"""
Constructor de payload para PDF de EPC.

Responsabilidad única: Construir el payload estructurado para generar PDFs.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.core.config import settings
from .helpers import age_from_ymd, parse_dt_maybe, list_to_lines

log = logging.getLogger(__name__)


class EPCPDFBuilder:
    """
    Construye el payload para generar PDF de EPC.
    
    Uso:
        builder = EPCPDFBuilder()
        payload = builder.build(epc_doc, patient, clinical, hce)
    """
    
    def build(
        self,
        epc_doc: Dict[str, Any],
        patient: Optional[Any] = None,
        clinical: Optional[Dict[str, Any]] = None,
        hce: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Arma el payload "amigable" para el PDF.
        
        Args:
            epc_doc: Documento EPC de MongoDB
            patient: Paciente de SQL (opcional)
            clinical: Datos clínicos derivados
            hce: HCE para expandir labs (opcional)
        """
        clinical = clinical or {}
        generated = epc_doc.get("generated") or {}
        gdata = generated.get("data") if isinstance(generated, dict) else None
        if not isinstance(gdata, dict):
            gdata = {}
        
        # Datos del paciente
        patient_info = self._extract_patient_info(patient, epc_doc)
        
        # Datos del médico
        medico_name = (epc_doc.get("medico_responsable") or "").strip()
        
        # Fecha de emisión
        fecha_emision = self._get_fecha_emision(epc_doc)
        
        # Título
        titulo = (epc_doc.get("titulo") or "Epicrisis de internación").strip()
        
        # Construir secciones
        sections = self._build_sections(gdata, generated, clinical, hce, epc_doc, titulo)
        
        # Info de clínica
        clinic_name = (
            getattr(settings, "CLINIC_NAME", None) or
            getattr(settings, "APP_NAME", None) or
            "Clínica / Consultorio"
        )
        clinic_address = getattr(settings, "CLINIC_ADDRESS", None) or ""
        
        return {
            "id": epc_doc.get("_id"),
            "created_at": epc_doc.get("created_at"),
            "updated_at": epc_doc.get("updated_at"),
            "fecha_emision": fecha_emision,
            "clinic": {"name": clinic_name, "address": clinic_address},
            "patient": patient_info,
            "doctor": {"full_name": medico_name or "", "matricula": ""},
            "sections": sections,
        }
    
    def _extract_patient_info(self, patient: Any, epc_doc: Dict) -> Dict[str, Any]:
        """Extrae información del paciente."""
        if not patient:
            return {
                "full_name": epc_doc.get("patient_id") or "",
                "dni": "",
                "age": "",
                "sex": "",
            }
        
        apellido = getattr(patient, "apellido", None)
        nombre = getattr(patient, "nombre", None)
        dni = getattr(patient, "dni", None)
        sexo = getattr(patient, "sexo", None)
        fn = getattr(patient, "fecha_nacimiento", None)
        edad = age_from_ymd(fn) if fn else None
        
        patient_full_name = ", ".join([
            p for p in [
                str(apellido).strip() if apellido else "",
                str(nombre).strip() if nombre else "",
            ] if p
        ]).strip()
        
        return {
            "full_name": patient_full_name or (epc_doc.get("patient_id") or ""),
            "dni": dni or "",
            "age": edad if edad is not None else "",
            "sex": sexo or "",
        }
    
    def _get_fecha_emision(self, epc_doc: Dict) -> Any:
        """Obtiene fecha de emisión."""
        fecha_emision = (
            epc_doc.get("fecha_emision") or
            epc_doc.get("updated_at") or
            epc_doc.get("created_at")
        )
        if isinstance(fecha_emision, str):
            dt = parse_dt_maybe(fecha_emision)
            fecha_emision = dt or fecha_emision
        return fecha_emision
    
    def _build_sections(
        self,
        gdata: Dict,
        generated: Dict,
        clinical: Dict,
        hce: Optional[Dict],
        epc_doc: Dict,
        titulo: str,
    ) -> Dict[str, Any]:
        """Construye las secciones del PDF."""
        sections: Dict[str, Any] = {"Título": titulo}
        
        # Datos clínicos
        clinical_text = self._build_clinical_section(clinical)
        if clinical_text:
            sections["Datos clínicos"] = clinical_text
        
        # Motivo y evolución
        motivo = gdata.get("motivo_internacion") or generated.get("motivo_internacion") or ""
        evolucion = gdata.get("evolucion") or generated.get("evolucion") or ""
        
        if motivo:
            sections["Motivo de internación"] = str(motivo)
        if evolucion:
            sections["Evolución"] = str(evolucion)
        
        # Procedimientos
        procedimientos = gdata.get("procedimientos") or generated.get("procedimientos") or []
        if procedimientos:
            procedimientos = self._process_procedimientos(procedimientos, hce, epc_doc)
            sections["Procedimientos"] = list_to_lines(procedimientos)
        
        # Interconsultas
        interconsultas = gdata.get("interconsultas") or generated.get("interconsultas") or []
        if interconsultas:
            sections["Interconsultas"] = list_to_lines(interconsultas)
        
        # Medicación
        med_text = self._build_medication_section(gdata, generated)
        if med_text:
            sections["Plan Terapéutico"] = med_text
        
        # Indicaciones y recomendaciones
        indicaciones_alta = gdata.get("indicaciones_alta") or generated.get("indicaciones_alta") or []
        recomendaciones = gdata.get("recomendaciones") or generated.get("recomendaciones") or []
        
        if indicaciones_alta:
            sections["Indicaciones de alta"] = list_to_lines(indicaciones_alta)
        if recomendaciones:
            sections["Recomendaciones"] = list_to_lines(recomendaciones)
        
        return sections
    
    def _build_clinical_section(self, clinical: Dict) -> str:
        """Construye sección de datos clínicos."""
        if not clinical:
            return ""
        
        lines: List[str] = []
        
        field_mapping = [
            ("numero_historia_clinica", "N° Historia Clínica"),
            ("admision_num", "N° Admisión"),
            ("protocolo", "Protocolo"),
        ]
        
        for field, label in field_mapping:
            if clinical.get(field):
                lines.append(f"{label}: {clinical.get(field)}")
        
        # Fechas
        fecha_ingreso = clinical.get("fecha_ingreso_display") or clinical.get("fecha_ingreso")
        if fecha_ingreso:
            lines.append(f"Fecha ingreso: {fecha_ingreso}")
        
        fecha_egreso = clinical.get("fecha_egreso_display") or clinical.get("fecha_egreso")
        if fecha_egreso:
            lines.append(f"Fecha egreso: {fecha_egreso}")
        
        # Ubicación
        for field in ["sector", "habitacion", "cama"]:
            if clinical.get(field):
                lines.append(f"{field.capitalize()}: {clinical.get(field)}")
        
        return "\n".join(lines)
    
    def _build_medication_section(self, gdata: Dict, generated: Dict) -> str:
        """Construye sección de medicación."""
        medicacion_internacion = gdata.get("medicacion_internacion") or generated.get("medicacion_internacion") or []
        medicacion_previa = gdata.get("medicacion_previa") or generated.get("medicacion_previa") or []
        medicacion_legacy = gdata.get("medicacion") or generated.get("medicacion") or []
        
        if medicacion_internacion or medicacion_previa:
            med_lines = []
            
            if medicacion_internacion:
                med_lines.append("Medicación durante internación:")
                for med in medicacion_internacion:
                    parts = [
                        med.get("farmaco", ""),
                        med.get("dosis", ""),
                        med.get("via", ""),
                        med.get("frecuencia", "")
                    ]
                    med_str = " ".join([p for p in parts if p]).strip()
                    med_lines.append(f"• {med_str}")
            
            if medicacion_previa:
                if med_lines:
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
            
            return "\n".join(med_lines)
        
        elif medicacion_legacy:
            return list_to_lines(medicacion_legacy)
        
        return ""
    
    def _process_procedimientos(
        self,
        procedimientos: List,
        hce: Optional[Dict],
        epc_doc: Dict,
    ) -> List:
        """Procesa y expande procedimientos según configuración."""
        if not hce:
            return procedimientos
        
        export_config = epc_doc.get("export_config", {})
        selected_labs = export_config.get("selected_labs", [])
        
        if not selected_labs:
            return procedimientos
        
        procedimientos_expandidos = []
        
        for proc_item in procedimientos:
            proc_str = str(proc_item) if not isinstance(proc_item, str) else proc_item
            
            # Detectar tag agrupado de labs
            if "Laboratorios realizados" in proc_str and "estudios)" in proc_str:
                parsed_hce = hce.get("ai_generated", {}) or {}
                parsed_data = parsed_hce.get("parsed_hce", {})
                procedimientos_hce = parsed_data.get("procedimientos", [])
                
                if procedimientos_hce:
                    labs_individuales = [
                        p for p in procedimientos_hce
                        if isinstance(p, dict)
                        and p.get("categoria") == "laboratorio"
                        and p.get("descripcion") in selected_labs
                    ]
                    
                    if labs_individuales:
                        procedimientos_expandidos.append("Laboratorios seleccionados:")
                        for lab in labs_individuales:
                            fecha = lab.get("fecha", "")[:16] if lab.get("fecha") else ""
                            desc = lab.get("descripcion", "Lab")
                            if fecha:
                                procedimientos_expandidos.append(f"  {fecha}: {desc}")
                            else:
                                procedimientos_expandidos.append(f"  {desc}")
                        continue
            
            procedimientos_expandidos.append(proc_item)
        
        return procedimientos_expandidos


# Función de conveniencia
def build_epc_pdf_payload(
    epc_doc: Dict[str, Any],
    patient: Optional[Any] = None,
    clinical: Optional[Dict[str, Any]] = None,
    hce: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Construye payload para PDF de EPC."""
    builder = EPCPDFBuilder()
    return builder.build(epc_doc, patient, clinical, hce)
