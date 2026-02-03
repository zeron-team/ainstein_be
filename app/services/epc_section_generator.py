"""
EPC Section Generator - Generación de EPC por secciones con prompts específicos.

Este módulo implementa una arquitectura de generación de EPC que:
1. Parsea la HCE en secciones individuales
2. Genera cada sección con su propio prompt y reglas específicas
3. Combina los resultados respetando ordenamientos (cronológico, alfabético)
"""
import re
import logging
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

log = logging.getLogger(__name__)


# =============================================================================
# PARSING DE HCE POR SECCIONES
# =============================================================================

def parse_hce_sections(hce_text: str) -> Dict[str, str]:
    """
    Parsea el texto de HCE y extrae secciones individuales.
    
    Returns:
        Dict con claves: ingreso, evolucion, diagnosticos, indicaciones, 
                         procedimientos, enfermeria, plantillas
    """
    sections = {
        "ingreso": "",
        "evolucion": "",
        "diagnosticos": "",
        "indicaciones": "",
        "procedimientos": "",
        "enfermeria": "",
        "plantillas": "",
        "full_text": hce_text,
    }
    
    # Patrones para detectar inicio de secciones
    section_patterns = [
        (r"={10,}\nINGRESO DE PACIENTE\n={10,}", "ingreso"),
        (r"={10,}\nEVOLUCIÓN MÉDICA\n={10,}", "evolucion"),
        (r"={10,}\nDIAGNÓSTICOS\n={10,}", "diagnosticos"),
        (r"={10,}\nINDICACIONES\n={10,}", "indicaciones"),
        (r"={10,}\nPROCEDIMIENTOS / ESTUDIOS\n={10,}", "procedimientos"),
        (r"={10,}\nHOJA DE ENFERMERÍA\n={10,}", "enfermeria"),
        (r"={10,}\nPLANTILLAS\n={10,}", "plantillas"),
    ]
    
    # Encontrar posiciones de cada sección
    positions = []
    for pattern, name in section_patterns:
        match = re.search(pattern, hce_text)
        if match:
            positions.append((match.start(), match.end(), name))
    
    # Ordenar por posición
    positions.sort(key=lambda x: x[0])
    
    # Extraer contenido de cada sección
    for i, (start, end, name) in enumerate(positions):
        if i + 1 < len(positions):
            next_start = positions[i + 1][0]
            sections[name] = hce_text[end:next_start].strip()
        else:
            sections[name] = hce_text[end:].strip()
    
    return sections



def extract_medications_from_indicaciones(indicaciones_text: str) -> List[Dict[str, Any]]:
    """
    Extrae medicamentos de la sección INDICACIONES de la HCE.
    Soporta múltiples formatos.
    """
    medications = []
    
    # Formato 1: Bloques estructurados con INDICACION #
    # Ejemplo: - [2025-12-16 11:51:54] INDICACION #4193729 • OMEPRAZOL (4/6)
    pattern1 = r"-\s*\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\]\s*INDICACION\s*#\d+\s*•\s*([^\n]+)"
    
    for match in re.finditer(pattern1, indicaciones_text):
        fecha = match.group(1)
        medicacion_line = match.group(2).strip()
        
        # Extraer nombre del fármaco
        farmaco_match = re.match(r"([^(]+)", medicacion_line)
        farmaco = farmaco_match.group(1).strip() if farmaco_match else medicacion_line
        
        # Buscar bloque siguiente para dosis/vía/frecuencia
        block_start = match.end()
        next_match = re.search(pattern1, indicaciones_text[block_start:])
        block_end = block_start + next_match.start() if next_match else len(indicaciones_text)
        block = indicaciones_text[block_start:block_end]
        
        dosis = ""
        via = ""
        frecuencia = ""
        
        dosis_match = re.search(r"Dosis:\s*(.+)", block)
        if dosis_match:
            dosis = dosis_match.group(1).strip()
        
        via_match = re.search(r"Vía:\s*(.+)", block)
        if via_match:
            via = via_match.group(1).strip()
            if via == "-":
                via = ""
        
        freq_match = re.search(r"Frecuencia:\s*(.+)", block)
        if freq_match:
            frecuencia = freq_match.group(1).strip()
        
        # Excluir soluciones
        is_solution = any(sol in farmaco.upper() for sol in [
            "SOLUCION FISIOLOGICA", "SOLUCION RINGER", "SOLUCION DEXTROSA", "GLUCOSALINA"
        ])
        
        if not is_solution and farmaco:
            medications.append({
                "tipo": "internacion",
                "farmaco": farmaco,
                "dosis": dosis,
                "via": via,
                "frecuencia": frecuencia,
            })
    
    return medications


def extract_medications_simple_format(hce_text: str) -> List[Dict[str, Any]]:
    """
    Extrae medicamentos del formato simple:
    Medicación: cefTRIAXona 1000mg Intravenoso 1 vez al día
    """
    medications = []
    
    # Patrón: Medicación: FARMACO DOSIS VIA FRECUENCIA
    pattern = r"Medicación:\s*([^\n]+)"
    
    for match in re.finditer(pattern, hce_text):
        line = match.group(1).strip()
        if not line:
            continue
        
        # Intentar parsear: "cefTRIAXona 1000mg Intravenoso 1 vez al día"
        # Patrón mejorado para capturar componentes
        parts_match = re.match(
            r"([A-Za-záéíóúñÁÉÍÓÚÑ]+)\s*"  # fármaco
            r"([\d.,]+\s*(?:mg|g|ml|mcg|UI|unidades)?)\s*"  # dosis
            r"(Oral|Intravenoso|IV|IM|SC|Subcutaneo|EV|Tópico|Inhalatoria)?\s*"  # vía
            r"(.+)?",  # frecuencia
            line, re.IGNORECASE
        )
        
        if parts_match:
            farmaco = parts_match.group(1).strip()
            dosis = (parts_match.group(2) or "").strip()
            via = (parts_match.group(3) or "").strip()
            frecuencia = (parts_match.group(4) or "").strip()
        else:
            # Fallback: tomar toda la línea como fármaco
            farmaco = line.split()[0] if line.split() else line
            dosis = ""
            via = ""
            frecuencia = " ".join(line.split()[1:]) if len(line.split()) > 1 else ""
        
        # Excluir soluciones
        is_solution = any(sol in farmaco.upper() for sol in [
            "SOLUCION", "RINGER", "DEXTROSA", "GLUCOSALINA", "PHP"
        ])
        
        if not is_solution and farmaco and len(farmaco) > 2:
            medications.append({
                "tipo": "internacion",
                "farmaco": farmaco,
                "dosis": dosis,
                "via": via,
                "frecuencia": frecuencia,
            })
    
    return medications


def extract_previous_medications(evolucion_text: str) -> List[Dict[str, Any]]:
    """
    Extrae medicación habitual/previa del paciente.
    Busca patrones como "MH:", "Medicación habitual:", etc.
    """
    medications = []
    
    patterns = [
        r"MH:\s*([^.]+\.)",
        r"Medicación habitual:\s*([^.]+\.)",
        r"medicación habitual:\s*([^.]+\.)",
        r"Tratamiento previo:\s*([^.]+\.)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, evolucion_text, re.IGNORECASE)
        if match:
            meds_text = match.group(1)
            meds_parts = re.split(r"[,;]", meds_text)
            
            for part in meds_parts:
                part = part.strip().rstrip(".")
                if not part or len(part) < 3:
                    continue
                
                farmaco_match = re.match(r"([a-záéíóúñ]+)\s*([\d,./]+\s*m?g)?(?:\s*(.+))?", part, re.IGNORECASE)
                
                if farmaco_match:
                    farmaco = farmaco_match.group(1).strip().capitalize()
                    dosis = (farmaco_match.group(2) or "").strip()
                    frecuencia = (farmaco_match.group(3) or "").strip()
                    
                    if farmaco and len(farmaco) > 2:
                        medications.append({
                            "tipo": "previa",
                            "farmaco": farmaco,
                            "dosis": dosis,
                            "via": "Oral",
                            "frecuencia": frecuencia,
                        })
            break
    
    return medications


def extract_procedures_from_hce(hce_text: str) -> List[Dict[str, Any]]:
    """
    Extrae procedimientos de la HCE. Soporta múltiples formatos.
    """
    procedures = []
    seen = set()
    
    # Formato 1: Con fecha/hora en corchetes
    # - [2025-12-16 11:51:10] PARTE QUIRURGICO #4193726
    #   ARTROPLASTIA TOTAL DE CADERA
    pattern1 = r"-\s*\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\]\s*([^\n]+)\n\s*([^\n]+)"
    
    for match in re.finditer(pattern1, hce_text):
        fecha_hora = match.group(1)
        tipo = match.group(2).strip()
        descripcion = match.group(3).strip()
        
        # Parsear fecha/hora
        try:
            dt = datetime.strptime(fecha_hora, "%Y-%m-%d %H:%M:%S")
            fecha_str = dt.strftime("%d/%m/%Y %H:%M")
        except:
            fecha_str = fecha_hora
        
        # Filtrar rutina de enfermería
        skip_keywords = ["SIGNOS VITALES", "CONTROL", "OBSERVACION", "VALORACION", 
                        "ADMINISTRACION", "PASE", "HOJA DE ENFERMERIA"]
        if any(kw in tipo.upper() for kw in skip_keywords):
            continue
        if any(kw in descripcion.upper() for kw in skip_keywords):
            continue
        
        key = descripcion.upper()[:50]
        if key not in seen:
            seen.add(key)
            procedures.append({
                "fecha": fecha_str,
                "descripcion": descripcion,
            })
    
    # Formato 2: Líneas simples "Procedimientos: DESCRIPCION"
    pattern2 = r"Procedimientos?:\s*([^\n]+)"
    
    for match in re.finditer(pattern2, hce_text):
        descripcion = match.group(1).strip()
        if not descripcion or len(descripcion) < 5:
            continue
        
        # Filtrar rutina
        skip_keywords = ["SIGNOS", "CONTROL", "VALORACION", "PASE"]
        if any(kw in descripcion.upper() for kw in skip_keywords):
            continue
        
        key = descripcion.upper()[:50]
        if key not in seen:
            seen.add(key)
            procedures.append({
                "fecha": "",
                "descripcion": descripcion,
            })
    
    return procedures


def extract_interconsultas_from_hce(hce_text: str) -> List[Dict[str, Any]]:
    """
    Extrae interconsultas de la HCE. Soporta múltiples formatos.
    """
    interconsultas = []
    seen_specialties = set()
    
    # Mapeo de términos a especialidades
    specialty_map = {
        "CLINICA MEDICA": "Clínica Médica",
        "TRAUMATOLOGIA": "Traumatología",
        "KINESIOLOGIA": "Kinesiología",
        "CARDIOLOGIA": "Cardiología",
        "UROLOGIA": "Urología",
        "NEUROLOGIA": "Neurología",
        "CIRUGIA": "Cirugía General",
        "GASTROENTEROLOGIA": "Gastroenterología",
        "NEUMONOLOGIA": "Neumonología",
        "INFECTOLOGIA": "Infectología",
        "UCI": "Terapia Intensiva",
        "UTI": "Terapia Intensiva",
    }
    
    # Formato 1: EVOLUCION DE INTERCONSULTA
    pattern1 = r"-\s*\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\]\s*EVOLUCION DE INTERCONSULTA"
    
    for match in re.finditer(pattern1, hce_text):
        fecha_hora = match.group(1)
        context = hce_text[match.end():match.end()+500]
        
        especialidad = None
        for key, val in specialty_map.items():
            if key.lower() in context.lower():
                especialidad = val
                break
        
        # Fallback por contenido
        if not especialidad:
            if "traumatol" in context.lower() or "cadera" in context.lower():
                especialidad = "Traumatología"
            elif "clinic" in context.lower():
                especialidad = "Clínica Médica"
            elif "kinesio" in context.lower():
                especialidad = "Kinesiología"
        
        if especialidad and especialidad not in seen_specialties:
            seen_specialties.add(especialidad)
            try:
                dt = datetime.strptime(fecha_hora, "%Y-%m-%d %H:%M:%S")
                fecha_str = dt.strftime("%d/%m/%Y %H:%M")
            except:
                fecha_str = fecha_hora
            
            interconsultas.append({
                "fecha": fecha_str,
                "especialidad": especialidad,
            })
    
    # Formato 2: INTERCONSULTA ESPECIALIDAD
    pattern2 = r"INTERCONSULTA\s+([A-Z\s]+?)(?:\n|Obs:|$)"
    
    for match in re.finditer(pattern2, hce_text):
        especialidad_raw = match.group(1).strip()
        especialidad = specialty_map.get(especialidad_raw.upper(), especialidad_raw.title())
        
        if especialidad and especialidad not in seen_specialties:
            seen_specialties.add(especialidad)
            interconsultas.append({
                "fecha": "",
                "especialidad": especialidad,
            })
    
    # Formato 3: Líneas simples "Interconsulta: ESPECIALIDAD"
    pattern3 = r"Interconsultas?:\s*([^\n]+)"
    
    for match in re.finditer(pattern3, hce_text):
        especialidad_raw = match.group(1).strip()
        if not especialidad_raw:
            continue
        
        especialidad = specialty_map.get(especialidad_raw.upper(), especialidad_raw.title())
        
        if especialidad and especialidad not in seen_specialties:
            seen_specialties.add(especialidad)
            interconsultas.append({
                "fecha": "",
                "especialidad": especialidad,
            })
    
    return interconsultas


# =============================================================================
# PROMPTS POR SECCIÓN
# =============================================================================

PROMPT_MOTIVO_EVOLUCION = """
Analiza el siguiente texto de Historia Clínica y genera:
1. motivo_internacion: Una frase clara del motivo de internación
2. evolucion: Texto médico técnico (2-4 párrafos) describiendo cronológicamente la evolución

REGLAS:
- Lenguaje médico técnico, estilo pase entre colegas
- Describir: antecedentes → motivo ingreso → evaluación inicial → tratamiento → evolución hasta el alta
- NO mencionar fármacos específicos en evolución (van en medicación)
- NO inventar datos que no estén en la HCE

Responde SOLO con JSON:
{{"motivo_internacion": "...", "evolucion": "..."}}

HCE:
\"\"\"
{hce_text}
\"\"\"
"""

PROMPT_DIAGNOSTICO = """
Del siguiente texto, extrae el diagnóstico principal CIE-10 si está disponible.

Responde SOLO con JSON:
{{"diagnostico_principal_cie10": "CÓDIGO - DESCRIPCIÓN" o ""}}

HCE:
\"\"\"
{hce_text}
\"\"\"
"""


# =============================================================================
# ORDENAMIENTO Y POST-PROCESAMIENTO
# =============================================================================

def sort_medications_alphabetically(medications: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Ordena medicamentos alfabéticamente por nombre de fármaco.
    Agrupa por tipo (internación primero, luego previa).
    
    AHORA retorna dict con:
    - "internacion": medicación durante internación
    - "previa": medicación habitual previa del paciente
    - "all": todas concatenadas (para compatibilidad)
    """
    # Separar por tipo
    internacion = [m for m in medications if m.get("tipo") != "previa"]
    previa = [m for m in medications if m.get("tipo") == "previa"]
    
    # Ordenar cada grupo alfabéticamente
    internacion.sort(key=lambda m: (m.get("farmaco") or "").lower())
    previa.sort(key=lambda m: (m.get("farmaco") or "").lower())
    
    # Eliminar duplicados por fármaco (mismo fármaco = mantener el primero)
    def deduplicate(meds: List[Dict]) -> List[Dict]:
        seen = set()
        unique = []
        for m in meds:
            farmaco = (m.get("farmaco") or "").lower().strip()
            if farmaco and farmaco not in seen:
                seen.add(farmaco)
                unique.append(m)
        return unique
    
    internacion = deduplicate(internacion)
    previa = deduplicate(previa)
    
    return {
        "internacion": internacion,
        "previa": previa,
        "all": internacion + previa  # Para compatibilidad con código antiguo
    }


def sort_procedures_chronologically(procedures: List[Dict[str, Any]]) -> List[str]:
    """
    Ordena procedimientos cronológicamente y formatea como strings.
    """
    # Intentar parsear fechas para ordenar
    def parse_date(p):
        fecha = p.get("fecha", "")
        try:
            # Formato esperado: "DD/MM/YYYY HH:MM"
            return datetime.strptime(fecha, "%d/%m/%Y %H:%M")
        except:
            try:
                return datetime.strptime(fecha, "%d/%m/%Y")
            except:
                return datetime.max
    
    sorted_procs = sorted(procedures, key=parse_date)
    
    # Formatear como strings
    result = []
    for p in sorted_procs:
        fecha = p.get("fecha", "")
        descripcion = p.get("descripcion", "") or p.get("tipo", "")
        if fecha and descripcion:
            result.append(f"{fecha} - {descripcion}")
        elif descripcion:
            result.append(descripcion)
    
    return result


def sort_interconsultas_alphabetically(interconsultas: List[Dict[str, Any]]) -> List[str]:
    """
    Ordena interconsultas alfabéticamente por especialidad.
    Formato: "DD/MM/YYYY HH:MM - Especialidad"
    """
    # Ordenar alfabéticamente por especialidad
    sorted_ics = sorted(interconsultas, key=lambda ic: (ic.get("especialidad") or "").lower())
    
    # Formatear como strings
    result = []
    for ic in sorted_ics:
        fecha = ic.get("fecha", "")
        especialidad = ic.get("especialidad", "")
        if fecha and especialidad:
            result.append(f"{fecha} - {especialidad}")
        elif especialidad:
            result.append(especialidad)
    
    return result


# =============================================================================
# GENERACIÓN PRINCIPAL
# =============================================================================

async def generate_epc_by_sections(
    hce_text: str,
    patient_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Genera EPC procesando la HCE por secciones.
    
    Flujo:
    1. Parsear HCE en secciones
    2. Extraer datos estructurados (medicación, procedimientos, interconsultas)
    3. Generar motivo/evolución con IA
    4. Ordenar y formatear todo
    5. Retornar estructura EPC completa
    """
    from app.services.ai_gemini_service import GeminiAIService
    
    log.info("[SectionGenerator] Iniciando generación por secciones")
    
    # DEBUG: Guardar muestra del texto para diagnóstico
    print(f"[SectionGenerator] HCE text length: {len(hce_text)}")
    print(f"[SectionGenerator] HCE primeros 500 chars: {hce_text[:500]}")
    
    # 1. Parsear secciones (para formato estructurado)
    sections = parse_hce_sections(hce_text)
    sections_found = [k for k,v in sections.items() if v and len(v) > 10]
    print(f"[SectionGenerator] Secciones con contenido: {sections_found}")
    
    # 2. Extraer datos estructurados - INTENTAR AMBOS FORMATOS
    
    # 2.a Medicación de internación - Formato estructurado
    meds_internacion = extract_medications_from_indicaciones(sections.get("indicaciones", ""))
    
    # 2.a.2 Si no encontró, probar formato simple en texto completo
    if not meds_internacion:
        meds_internacion = extract_medications_simple_format(hce_text)
    
    print(f"[SectionGenerator] Medicamentos internación: {len(meds_internacion)}")
    if meds_internacion:
        print(f"[SectionGenerator] Meds encontrados: {[m['farmaco'] for m in meds_internacion[:5]]}")
    
    # 2.b Medicación previa
    meds_previa = extract_previous_medications(sections.get("evolucion", "") + sections.get("plantillas", "") + hce_text)
    print(f"[SectionGenerator] Medicamentos previos: {len(meds_previa)}")
    
    # 2.c Procedimientos
    procedures = extract_procedures_from_hce(hce_text)
    print(f"[SectionGenerator] Procedimientos: {len(procedures)}")
    if procedures:
        print(f"[SectionGenerator] Procs encontrados: {[p['descripcion'][:30] for p in procedures[:5]]}")
    
    # 2.d Interconsultas
    interconsultas = extract_interconsultas_from_hce(hce_text)
    print(f"[SectionGenerator] Interconsultas: {len(interconsultas)}")
    
    # 3. Generar motivo/evolución con IA
    ai = GeminiAIService()
    prompt = PROMPT_MOTIVO_EVOLUCION.format(hce_text=hce_text[:15000])  # Limitar tamaño
    
    try:
        raw_result = await ai.generate_epc(prompt)
        
        # Parsear respuesta JSON
        motivo = ""
        evolucion = ""
        
        if isinstance(raw_result, dict):
            if "json" in raw_result:
                data = raw_result["json"]
            elif "raw_text" in raw_result:
                import json
                try:
                    text = raw_result["raw_text"]
                    # Limpiar markdown
                    if "```" in text:
                        text = re.sub(r"```json\s*", "", text)
                        text = re.sub(r"```\s*", "", text)
                    data = json.loads(text)
                except:
                    data = {}
            else:
                data = raw_result
            
            motivo = data.get("motivo_internacion", "")
            evolucion = data.get("evolucion", "")
        
        log.info(f"[SectionGenerator] Motivo/Evolución generados")
    except Exception as e:
        log.error(f"[SectionGenerator] Error generando motivo/evolución: {e}")
        motivo = ""
        evolucion = ""
    
    # 4. Extraer diagnóstico de la HCE directamente
    diagnostico = ""
    diag_match = re.search(r"•\s*([A-Z][^\n]+\([A-Z0-9.]+\))", hce_text)
    if diag_match:
        diagnostico = diag_match.group(1).strip()
    
    # 5. Ordenar y formatear
    # 5.a Medicación: ordenar alfabéticamente
    all_medications = meds_internacion + meds_previa
    medications_dict = sort_medications_alphabetically(all_medications)
    
    # 5.b Procedimientos: ordenar cronológicamente
    sorted_procedures = sort_procedures_chronologically(procedures)
    
    # 5.c Interconsultas: ordenar alfabéticamente
    sorted_interconsultas = sort_interconsultas_alphabetically(interconsultas)
    
    # 6. Construir respuesta final
    result = {
        "motivo_internacion": motivo,
        "diagnostico_principal_cie10": diagnostico,
        "evolucion": evolucion,
        "procedimientos": sorted_procedures,
        "interconsultas": sorted_interconsultas,
        "medicacion_internacion": medications_dict["internacion"],  # Nueva - durante internación
        "medicacion_previa": medications_dict["previa"],            # Nueva - habitual previa
        "medicacion": medications_dict["all"],                      # Compatibilidad
        "indicaciones_alta": [],  # El médico lo completa manualmente
        "notas_alta": [],
        "_generated_by": "section_generator",
        "_sections_parsed": list(sections.keys()),
    }
    
    log.info(f"[SectionGenerator] EPC generada: procedimientos={len(sorted_procedures)}, "
             f"interconsultas={len(sorted_interconsultas)}, "
             f"medicacion_internacion={len(medications_dict['internacion'])}, "
             f"medicacion_previa={len(medications_dict['previa'])}")
    
    # 7. ⚠️ POST-PROCESAMIENTO OBLIGATORIO: Aplicar reglas críticas (incluida regla de óbito)
    from app.services.ai_langchain_service import _post_process_epc_result
    result = _post_process_epc_result(result)
    log.info("[SectionGenerator] Post-procesamiento de reglas aplicado (incluida regla de óbito)")
    
    return result
