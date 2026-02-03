"""
HCE Ainstein Parser - Parsing and Chunking for Ainstein HCE JSON

Este módulo es responsable de:
1. Parsear el JSON de HCE recibido desde el WebService de Markey
2. Extraer secciones relevantes (ingreso, evoluciones, indicaciones, etc.)
3. Crear chunks semánticos para embeddings y RAG

Estrategia de chunking:
- Por tipo de registro (entrTipoRegistro)
- Metadata rica: fecha, tipo, autor, contenido
- Chunks auto-contenidos para búsqueda semántica
"""

from __future__ import annotations
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

log = logging.getLogger(__name__)


class RegistryType(str, Enum):
    """Tipos de registro en la historia clínica."""
    INGRESO = "INGRESO DE PACIENTE"
    EVOLUCION_MEDICA = "EVOLUCION MEDICA (A CARGO)"
    EVOLUCION_INTERCONSULTA = "EVOLUCION DE INTERCONSULTA"
    INDICACION = "INDICACION"
    HOJA_ENFERMERIA = "HOJA DE ENFERMERIA"
    CONTROL_ENFERMERIA = "CONTROL DE ENFERMERIA"
    BALANCE_HIDROELECTROLITICO = "BALANCE HIDROELECTROLITICO"


@dataclass
class Chunk:
    """Representa un fragmento de texto para embedding."""
    chunk_id: str
    content: str
    metadata: Dict[str, Any]
    registry_type: Optional[str] = None
    fecha_atencion: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario para almacenamiento."""
        return {
            "chunk_id": self.chunk_id,
            "content": self.content,
            "metadata": self.metadata,
            "registry_type": self.registry_type,
            "fecha_atencion": self.fecha_atencion.isoformat() if self.fecha_atencion else None
        }


@dataclass
class HCESections:
    """Secciones extraídas de la HCE."""
    ingreso: str = ""
    motivo_real: str = ""  # Fuente: Triage / Motivo Consulta
    evoluciones_medicas: List[Dict[str, Any]] = field(default_factory=list)
    evoluciones_todas: List[str] = field(default_factory=list)  # Evolución cronológica completa (100% lectura)
    interconsultas: List[Dict[str, Any]] = field(default_factory=list)
    indicaciones_farmacologicas: List[Dict[str, Any]] = field(default_factory=list)
    medicacion_previa: List[Dict[str, Any]] = field(default_factory=list)  # Antecedentes farmacológicos
    procedimientos: List[Dict[str, Any]] = field(default_factory=list)
    laboratorios: List[Dict[str, Any]] = field(default_factory=list)  # Procedimientos de laboratorio
    plantillas: List[Dict[str, Any]] = field(default_factory=list)
    diagnosticos: List[str] = field(default_factory=list)


@dataclass
class ParsedHCE:
    """HCE parseada con metadata."""
    hce_id: str
    patient_id: str
    admission_id: str
    episodio: Dict[str, Any]
    sections: HCESections
    historia: List[Dict[str, Any]]
    edad: int
    sexo: str
    fecha_ingreso: datetime
    fecha_egreso: Optional[datetime] = None
    dias_estada: int = 0
    tipo_alta: Optional[str] = None


class HCEAinsteinParser:
    """Parser principal para HCE de Ainstein en formato JSON."""
    
    def parse_from_ainstein(self, hce_json: Dict[str, Any]) -> ParsedHCE:
        """
        Parsea el JSON completo de HCE desde Ainstein.
        
        Args:
            hce_json: JSON completo con estructura Ainstein
            
        Returns:
            ParsedHCE con toda la información estructurada
        """
        ainstein_data = hce_json.get("ainstein", {})
        episodio = ainstein_data.get("episodio", {})
        historia = ainstein_data.get("historia", [])
        
        # Extraer metadata del episodio
        hce_id = hce_json.get("_id", "")
        patient_id = hce_json.get("patient_id", "")
        admission_id = hce_json.get("admission_id", "")
        
        edad = episodio.get("paciEdad", 0)
        sexo = episodio.get("paciSexo", "")
        
        fecha_ingreso_str = episodio.get("inteFechaIngreso")
        fecha_egreso_str = episodio.get("inteFechaEgreso")
        
        fecha_ingreso = self._parse_datetime(fecha_ingreso_str) if fecha_ingreso_str else datetime.now()
        fecha_egreso = self._parse_datetime(fecha_egreso_str) if fecha_egreso_str else None
        
        dias_estada = episodio.get("inteDiasEstada", 0)
        tipo_alta = episodio.get("taltDescripcion")
        
        # Extraer secciones
        sections = self.extract_sections(historia)
        
        parsed = ParsedHCE(
            hce_id=hce_id,
            patient_id=patient_id,
            admission_id=admission_id,
            episodio=episodio,
            sections=sections,
            historia=historia,
            edad=edad,
            sexo=sexo,
            fecha_ingreso=fecha_ingreso,
            fecha_egreso=fecha_egreso,
            dias_estada=dias_estada,
            tipo_alta=tipo_alta
        )
        
        log.info(f"[HCEAinsteinParser] Parsed HCE {hce_id}: {len(historia)} entries, {dias_estada} days")
        
        return parsed
    
    def extract_sections(self, historia: List[Dict[str, Any]]) -> HCESections:
        """
        Extrae y organiza las secciones de la historia clínica.
        
        Args:
            historia: Lista de entradas de la historia
            
        Returns:
            HCESections con contenido organizado
        """
    def extract_sections(self, historia: List[Dict[str, Any]]) -> HCESections:
        """
        Extrae y categoriza secciones de la historia clínica.
        Implementa extracción inteligente de laboratorios y lectura 100%.
        """
        sections = HCESections()
        
        # Ordenar cronológicamente
        historia_sorted = sorted(historia, key=lambda x: x.get("entrFechaAtencion") or "")
        
        # 1. Extracción de Motivo Real (Primeros registros)
        for entry in historia_sorted[:3]:  # Mirar los primeros 3 registros
            tipo = entry.get("entrTipoRegistro", "")
            contenido = entry.get("entrEvolucion", "")
            
            if contenido and (tipo == RegistryType.INGRESO or "TRIAGE" in tipo or "ADMIS" in tipo):
                # Intentar extraer "Motivo de Consulta" explícito
                import re
                match = re.search(r"(?:motivo de consulta|motivo ingres|consulta por|mc)[:\s]+([^.\n]+)", contenido, re.IGNORECASE)
                if match:
                    sections.motivo_real = match.group(1).strip()
                    break
        
        # Si no encontró motivo explícito, usar primeros caracteres del ingreso
        if not sections.motivo_real:
            for entry in historia_sorted:
                if entry.get("entrTipoRegistro") == RegistryType.INGRESO:
                    sections.motivo_real = (entry.get("entrEvolucion", "") or "")[:300] + "..."
                    break

        for entry in historia_sorted:
            tipo = entry.get("entrTipoRegistro", "")
            fecha = entry.get("entrFechaAtencion", "")
            evolucion = entry.get("entrEvolucion", "")
            
            # 2. Acumular Evoución Completa (100% Lectura)
            # Excluimos balances y controles rutinarios de enfermería para reducir ruido, 
            # pero mantenemos TODO el texto médico/clínico relevante.
            if evolucion and tipo not in [RegistryType.BALANCE_HIDROELECTROLITICO, RegistryType.CONTROL_ENFERMERIA]:
                 sections.evoluciones_todas.append(f"[{fecha}] ({tipo})\n{evolucion}")

            # Ingreso
            if tipo == RegistryType.INGRESO:
                if evolucion and not sections.ingreso:
                    sections.ingreso = evolucion
                plantillas = entry.get("plantillas", [])
                if plantillas:
                    sections.plantillas.extend(plantillas)
            
            # Evoluciones médicas
            elif tipo == RegistryType.EVOLUCION_MEDICA:
                if evolucion:
                    sections.evoluciones_medicas.append({
                        "fecha": fecha,
                        "contenido": evolucion,
                        "plantillas": entry.get("plantillas", [])
                    })
            
            # Interconsultas
            elif tipo == RegistryType.EVOLUCION_INTERCONSULTA:
                diagnosticos = entry.get("diagnosticos", [])
                if evolucion:
                    sections.interconsultas.append({
                        "fecha": fecha,
                        "contenido": evolucion,
                        "diagnosticos": diagnosticos
                    })
            
            # Indicaciones y Procedimientos
            elif tipo == RegistryType.INDICACION:
                # Medicación
                indicaciones = entry.get("indicacionFarmacologica") or []
                if indicaciones:
                    for ind in indicaciones:
                        sections.indicaciones_farmacologicas.append({
                            "fecha": fecha,
                            "farmaco": ind
                        })
                
                # Procedimientos
                # 3. Clasificación Inteligente de Laboratorios
                procs = entry.get("indicacionProcedimientos") or []
                for proc in procs:
                    desc = proc.get("procDescripcion", "").strip()
                    if not desc:
                        continue
                        
                    item = {
                        "fecha": fecha,
                        "descripcion": desc,
                        "detalle": proc.get("enprObservacion", "")
                    }
                    
                    desc_upper = desc.upper()
                    # Palabras clave para laboratorio
                    keywords_lab = ["LABORATORIO", "HEMOGRAMA", "ORINA", "UROCULTIVO", "CULTIVO", "PERFIL", "QUIMICA", "DOSEJE", "SEROLOGIA"]
                    
                    if any(k in desc_upper for k in keywords_lab):
                         sections.laboratorios.append(item)
                    else:
                         sections.procedimientos.append(item)

            # Diagnósticos
            diagnosticos = entry.get("diagnosticos") or []
            for diag in diagnosticos:
                desc = diag.get("diagDescripcion", "")
                if desc and desc not in sections.diagnosticos:
                    sections.diagnosticos.append(desc)
                    
        return sections
    
    def chunk_by_registry_type(
        self,
        historia: List[Dict[str, Any]],
        hce_id: str
    ) -> List[Chunk]:
        """
        Crea chunks inteligentes por tipo de registro.
        
        Estrategia:
        - INGRESO: 1 chunk con toda la información de ingreso
        - EVOLUCION MEDICA: 1 chunk por evolución
        - EVOLUCION INTERCONSULTA: 1 chunk por interconsulta
        - INDICACION: Agrupar por fecha (todas las indicaciones del mismo día)
        
        Args:
            historia: Lista de entradas de la historia
            hce_id: ID de la HCE
            
        Returns:
            Lista de chunks listos para embedding
        """
        chunks: List[Chunk] = []
        chunk_counter = 0
        
        # Agrupar indicaciones por fecha
        indicaciones_por_fecha: Dict[str, List[Dict]] = {}
        
        for entry in historia:
            tipo = entry.get("entrTipoRegistro", "")
            fecha_atencion_str = entry.get("entrFechaAtencion")
            fecha_atencion = self._parse_datetime(fecha_atencion_str) if fecha_atencion_str else None
            
            # INGRESO DE PACIENTE
            if tipo == RegistryType.INGRESO:
                evolucion = entry.get("entrEvolucion", "")
                if evolucion:
                    chunk_id = f"{hce_id}_chunk_{chunk_counter:04d}"
                    chunk_counter += 1
                    
                    chunks.append(Chunk(
                        chunk_id=chunk_id,
                        content=evolucion,
                        metadata={
                            "hce_id": hce_id,
                            "entry_codigo": entry.get("entrCodigo"),
                            "tipo_registro": tipo,
                            "seccion": "ingreso"
                        },
                        registry_type=tipo,
                        fecha_atencion=fecha_atencion
                    ))
            
            # EVOLUCION MEDICA
            elif tipo == RegistryType.EVOLUCION_MEDICA:
                evolucion = entry.get("entrEvolucion", "")
                if evolucion:
                    chunk_id = f"{hce_id}_chunk_{chunk_counter:04d}"
                    chunk_counter += 1
                    
                    chunks.append(Chunk(
                        chunk_id=chunk_id,
                        content=evolucion,
                        metadata={
                            "hce_id": hce_id,
                            "entry_codigo": entry.get("entrCodigo"),
                            "tipo_registro": tipo,
                            "seccion": "evolucion_medica"
                        },
                        registry_type=tipo,
                        fecha_atencion=fecha_atencion
                    ))
            
            # EVOLUCION INTERCONSULTA
            elif tipo == RegistryType.EVOLUCION_INTERCONSULTA:
                evolucion = entry.get("entrEvolucion", "")
                diagnosticos = entry.get("diagnosticos", [])
                
                if evolucion:
                    # Incluir diagnósticos en el contenido
                    content = evolucion
                    if diagnosticos:
                        diag_text = " | ".join([d.get("diagDescripcion", "") for d in diagnosticos])
                        content += f"\n\nDIAGNÓSTICOS: {diag_text}"
                    
                    chunk_id = f"{hce_id}_chunk_{chunk_counter:04d}"
                    chunk_counter += 1
                    
                    chunks.append(Chunk(
                        chunk_id=chunk_id,
                        content=content,
                        metadata={
                            "hce_id": hce_id,
                            "entry_codigo": entry.get("entrCodigo"),
                            "tipo_registro": tipo,
                            "seccion": "interconsulta",
                            "diagnosticos": [d.get("diagDescripcion", "") for d in diagnosticos]
                        },
                        registry_type=tipo,
                        fecha_atencion=fecha_atencion
                    ))
            
            # INDICACIONES - Agrupar por fecha
            elif tipo == RegistryType.INDICACION:
                fecha_key = fecha_atencion_str[:10] if fecha_atencion_str else "sin_fecha"
                if fecha_key not in indicaciones_por_fecha:
                    indicaciones_por_fecha[fecha_key] = []
                indicaciones_por_fecha[fecha_key].append(entry)
        
        # Crear chunks de indicaciones agrupadas por fecha
        for fecha_key, indicaciones in indicaciones_por_fecha.items():
            content_parts = []
            
            for ind in indicaciones:
                # Farmacológicas
                farm = ind.get("indicacionFarmacologica", [])
                if farm:
                    for med in farm:
                        gene = med.get("geneDescripcion", "")
                        dosis = med.get("enmeDosis", "")
                        via = med.get("meviDescripcion", "")
                        frec = med.get("mefrDescripcion", "")
                        content_parts.append(f"MEDICACIÓN: {gene} {dosis} {via} {frec}")
                
                # Procedimientos
                proc = ind.get("indicacionProcedimientos", [])
                if proc:
                    for p in proc:
                        desc = p.get("procDescripcion", "")
                        obs = p.get("enprObservacion", "")
                        content_parts.append(f"PROCEDIMIENTO: {desc} - {obs}")
                
                # Enfermería
                enf = ind.get("indicacionEnfermeria", [])
                if enf:
                    for e in enf:
                        desc = e.get("indiDescripcion", "")
                        content_parts.append(f"ENFERMERÍA: {desc}")
            
            if content_parts:
                content = f"INDICACIONES del {fecha_key}:\n" + "\n".join(content_parts)
                chunk_id = f"{hce_id}_chunk_{chunk_counter:04d}"
                chunk_counter += 1
                
                fecha_dt = self._parse_datetime(fecha_key) if fecha_key != "sin_fecha" else None
                
                chunks.append(Chunk(
                    chunk_id=chunk_id,
                    content=content,
                    metadata={
                        "hce_id": hce_id,
                        "tipo_registro": "INDICACION_AGRUPADA",
                        "seccion": "indicaciones",
                        "fecha": fecha_key,
                        "num_indicaciones": len(indicaciones)
                    },
                    registry_type="INDICACION",
                    fecha_atencion=fecha_dt
                ))
        
        log.info(f"[HCEAinsteinParser] Created {len(chunks)} chunks from {len(historia)} entries")
        
        return chunks
    
    def _parse_datetime(self, date_str: str) -> Optional[datetime]:
        """Parsea string de fecha ISO a datetime."""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception as e:
            log.warning(f"[HCEAinsteinParser] Error parsing date '{date_str}': {e}")
            return None
