"""
Parser de HCE JSON Estructurado (Ainstein).

Este módulo parsea la estructura JSON de HCE que viene de Ainstein
y extrae medicación, procedimientos, interconsultas, etc.
"""
import re
import json
import logging
import html
from typing import Any, Dict, List, Optional
from datetime import datetime

log = logging.getLogger(__name__)


# Medical acronyms/abbreviations that should stay ALL CAPS
_KEEP_UPPER = {
    "TAC", "RMN", "RX", "ECG", "EEG", "EMG", "VCC", "VEDA", "CPRE",
    "PCR", "LDH", "VSG", "TSH", "HIV", "HCV", "HBV", "PSA", "CEA",
    "ARM", "PET", "SPECT", "DLEE", "AKM", "JJ", "SNC", "UTI",
    "CVC", "DIU", "VNI", "HTA", "EPOC", "IAM", "ACV", "TVP", "TEP",
    "IC", "IR", "IV", "VO", "IM", "SC", "EV", "IOT", "CIE10",
    "II", "III", "IV", "VI", "VII", "VIII", "IX", "XI", "XII",
}
_LOWERCASE_WORDS = {"de", "del", "con", "por", "para", "en", "el", "la", "al", "los", "las", "un", "una", "y", "o", "e"}

# =============================================================================
# GLOBAL LAB / BLOOD TEST KEYWORDS  —  These should NEVER appear in "Estudios"
# =============================================================================
_LAB_KEYWORDS_GLOBAL = [
    # Hematología
    "HEMOGRAMA", "HEMATOCRITO", "HEMOGLOBINA", "LEUCOCITOS", "PLAQUETAS",
    "RETICULOCITOS", "FROTIS", "MORFOLOGIA", "RECUENTO",
    # Bioquímica / Metabolismo
    "GLUCEMIA", "GLUCOSA", "CREATININA", "UREMIA", "UREA", "IONOGRAMA",
    "HEPATOGRAMA", "CALCEMIA", "MAGNESIO EN SANGRE", "MAGNESIO",
    "FOSFATEMIA", "FOSFORO", "FÓSFORO", "POTASIO", "SODIO", "CLORO",
    "BICARBONATO", "CALCIO IONICO", "CALCIO IÓNICO", "CALCIO", "LITIO",
    "COLESTEROL", "TRIGLICERIDOS", "TRIGLICÉRIDOS", "HDL", "LDL", "VLDL",
    "URICEMIA", "ACIDO URICO", "ÁCIDO ÚRICO",
    "BILIRRUBINA", "PROTEINAS TOTALES", "PROTEÍNAS TOTALES",
    "ALBUMINA", "ALBÚMINA", "GLOBULINAS", "PREALBUMINA",
    "AMILASA", "LIPASA", "LDH", "CPK", "CK-MB", "TROPONINA",
    "TRANSAMINASAS", "GOT", "GPT", "TGO", "TGP", "ALT", "AST",
    "FOSFATASA ALCALINA", "FOSFATASA", "GGT", "GAMMA GT",
    # Gases / Ácido-base
    "ACIDO BASE", "ÁCIDO BASE", "GASOMETRIA", "GASOMETRÍA",
    "EQUILIBRIO ACIDO BASE", "EAB", "PH ARTERIAL",
    "LACTICO", "LÁCTICO", "LACTATO",
    # Coagulación
    "COAGULOGRAMA", "TIEMPO DE PROTROMBINA", "TP", "KPTT", "TPPA",
    "DIMERO D", "DÍMERO D", "FIBRINOGENO", "FIBRINÓGENO",
    "RIN", "INR", "ANTI XA",
    # Inflamación / Marcadores
    "PCR ULTRASENSIBLE", "VSG", "ERITROSEDIMENTACION", "ERITROSEDIMENTACIÓN",
    "FERRITINA", "TRANSFERRINA", "PROCALCITONINA",
    # Hormonas / Endocrinología
    "TSH", "T3", "T4", "CORTISOL", "INSULINA", "HORMONA", "HORMONAS",
    "PTH", "PARATOHORMONA", "PROLACTINA", "TESTOSTERONA",
    # Serología / Microbiología
    "HEMOCULTIVO", "HEMOCULTIVOS", "UROCULTIVO", "COPROCULTIVO",
    "CULTIVO", "HISOPADO", "ANTIBIOGRAMA",
    "TEST RAPIDO", "TEST RÁPIDO", "ANTIGENO", "ANTÍGENO",
    "SARS-COV", "SARS COV", "COVID", "INFLUENZA",
    "HIV", "VIH", "HCV", "HBV", "HEPATITIS", "VDRL", "FTA-ABS",
    "MONOTEST", "PAUL BUNNEL",
    # Vitaminas / Minerales
    "VITAMINA", "VIT B12", "VIT D", "ACIDO FOLICO", "ÁCIDO FÓLICO",
    "HIERRO SERICO", "HIERRO SÉRICO", "TIBC",
    # Función renal / Orina
    "ORINA COMPLETA", "SEDIMENTO URINARIO", "PROTEINURIA",
    "CLEARANCE", "CREATININURIA", "MICROALBUMINURIA",
    # Función hepática adicional
    "HEPATOGRAMA", "PERFIL HEPATICO", "PERFIL HEPÁTICO",
    # Marcadores tumorales
    "PSA", "CEA", "CA 19-9", "CA 125", "ALFA FETO",
    # Otros análisis de sangre
    "GRUPO Y FACTOR", "GRUPO SANGUINEO", "GRUPO SANGUÍNEO",
    "COOMBS", "PRUEBA CRUZADA", "TIPIFICACION",
    "LABORATORIO",
    # Palabras genéricas que indican lab
    "DOSAJE", "DETERMINACION DE", "DETERMINACIÓN DE",
    "EN SANGRE", "EN SUERO", "EN PLASMA", "SERICO", "SÉRICO",
]


def _is_lab_item(text: str) -> bool:
    """Returns True if the text corresponds to a lab/blood test, NOT a diagnostic study."""
    if not text:
        return False
    t = text.upper().strip()
    # Remove parenthetical dates for cleaner matching
    t = re.sub(r'\s*\([^)]*\)\s*$', '', t).strip()
    return any(kw in t for kw in _LAB_KEYWORDS_GLOBAL)


def _group_studies_by_name(studies: list) -> list:
    """
    REGLA DE ORO - Estudios: Agrupar estudios repetidos por nombre, consolidando fechas.
    
    Entrada:  ["TC tórax (11/03/2026)", "TC tórax (12/03/2026)", "Eco abdominal (11/03/2026)"]
    Salida:   ["TC tórax (11/03/2026, 12/03/2026)", "Eco abdominal (11/03/2026)"]
    """
    if not studies:
        return studies
    
    from collections import OrderedDict
    agrupados = OrderedDict()
    
    for est in studies:
        if not isinstance(est, str):
            continue
        
        # Extraer fecha(s) del final: "Nombre (dd/mm/yyyy)" o "Nombre (dd/mm/yyyy, dd/mm/yyyy)"
        fechas_match = re.search(r'\(([^)]+)\)\s*$', est)
        if fechas_match:
            nombre = re.sub(r'\s*\([^)]*\)\s*$', '', est).strip()
            fechas_raw = fechas_match.group(1)
            # Puede haber múltiples fechas ya consolidadas
            fechas = [f.strip() for f in fechas_raw.split(',') if re.match(r'\d{1,2}/\d{1,2}/\d{2,4}', f.strip())]
        else:
            nombre = est.strip()
            fechas = []
        
        # Normalizar nombre para agrupar (case-insensitive, sin acentos extras)
        nombre_key = nombre.lower().strip()
        
        if nombre_key not in agrupados:
            agrupados[nombre_key] = {"nombre": nombre, "fechas": []}
        
        for f in fechas:
            if f not in agrupados[nombre_key]["fechas"]:
                agrupados[nombre_key]["fechas"].append(f)
    
    # Construir lista final
    resultado = []
    for entry in agrupados.values():
        if entry["fechas"]:
            try:
                from datetime import datetime
                fechas_ord = sorted(entry["fechas"], key=lambda f: datetime.strptime(f, "%d/%m/%Y"))
            except:
                fechas_ord = entry["fechas"]
            resultado.append(f"{entry['nombre']} ({', '.join(fechas_ord)})")
        else:
            resultado.append(entry["nombre"])
    
    return resultado



def _medical_title_case(text: str) -> str:
    """
    Convert ALL CAPS medical text to Title Case, preserving medical acronyms.
    E.g.: "LITOTRICIA URETERAL ENDOSCOPICA CON CATETER JJ" → "Litotricia Ureteral Endoscopica Con Cateter JJ"
    """
    if not text:
        return text
    
    words = text.split()
    result = []
    for i, word in enumerate(words):
        # Strip punctuation for checking, preserve it in output
        clean = word.strip("(),.-;:")
        prefix = word[:len(word) - len(word.lstrip("(),.-;:"))]
        suffix = word[len(word.rstrip("(),.-;:")):]  if word.rstrip("(),.-;:") != word else ""
        
        if clean.upper() in _KEEP_UPPER:
            result.append(prefix + clean.upper() + suffix)
        elif i > 0 and clean.lower() in _LOWERCASE_WORDS:
            result.append(prefix + clean.lower() + suffix)
        else:
            # Title case: first letter uppercase, rest lowercase
            result.append(prefix + clean.capitalize() + suffix)
    
    return " ".join(result)


# Prepositions/connectors that indicate an incomplete name if they're the last word
_TRAILING_PREPOSITIONS = {"POR", "PARA", "DE", "DEL", "CON", "EN", "A", "AL", "Y", "O", "E", "SIN", "SOBRE"}


def _is_incomplete_procedure(descripcion: str) -> bool:
    """
    Detect incomplete/truncated procedure names.
    E.g.: "CIRUGIA POR", "CIRUGIA PARA", "TRATAMIENTO DE"
    These end with a preposition, which makes no sense as a standalone name.
    """
    if not descripcion:
        return True
    words = descripcion.upper().strip().split()
    if not words:
        return True
    # A name ending with a preposition is incomplete
    if words[-1] in _TRAILING_PREPOSITIONS:
        return True
    # A single generic word without specificity is too vague
    if len(words) == 1 and words[0] in {"CIRUGIA", "TRATAMIENTO", "OPERACION", "PROCEDIMIENTO", "CONSULTA",
                                          "ESTUDIO", "EVALUACION", "CONTROL", "TERAPIA"}:
        return True
    return False


# =============================================================================
# CATEGORIZACIÓN DE PROCEDIMIENTOS
# =============================================================================

PROCEDURE_CATEGORIES = {
    # 🔬 Laboratorio
    "laboratorio": [
        "LABORATORIO", "HEMOGRAMA", "COAGULACION DEL PLASMA", "BIOQUIMICA", 
        "ORINA COMPLETA", "CULTIVO", "SEROLOGIA", "IONOGRAMA", "GASOMETRIA", 
        "PCR", "HEPATOGRAMA", "GLUCEMIA CAPILAR",
    ],
    # 📷 Estudios por imágenes  
    "imagen": [
        "RX ", "RADIOGRAFIA", "TAC ", "TOMOGRAFIA", "RMN ", "RESONANCIA",
        "ECOGRAFIA", "ECOCARDIOGRAMA", "CENTELLOGRAMA", "SPECT",
        "MAMOGRAFIA", "DENSITOMETRIA", "DOPPLER",
    ],
    # 🔍 Estudios diagnósticos
    "estudio": [
        "VEDA ", "VEDA DIAGNOSTICA", "VCC", "ENDOSCOPIA", "COLONOSCOPIA", 
        "BRONCOSCOPIA", "BIOPSIA", "PUNCION", "ARTROSCOPIA", "LAPAROSCOPIA", 
        "ELECTROCARDIOGRAMA", "HOLTER", "ERGOMETRIA", "ECODOPPLER",
        "VALORACION DLEE",
    ],
    # 👨‍⚕️ Interconsultas
    "interconsulta": [
        "INTERCONSULTA", "HEMATOLOGIA - CONSULTA", "CONSULTA", 
        "EVALUACION POR", "VALORACION POR",
    ],
    # ⚕️ Procedimientos quirúrgicos/invasivos  
    "quirurgico": [
        "CIRUGIA", "COLECISTECTOMIA", "APENDICECTOMIA", "HERNIOPLASTIA",
        "ARTROPLASTIA", "INTERNACION UCI", "INTERNACION UTI", " ARM",
        "CATETER", "VIA CENTRAL", "DRENAJE", "TUBO", "SONDA VESICAL", 
        "INTUBACION", "RESECCION",
    ],
    # 💉 Curaciones y tratamientos (importantes, NO agrupar)
    "tratamiento": [
        "CURACION", "TRANSFUSION", "NEBULIZACION", "OXIGENOTERAPIA",
        "DIALISIS", "QUIMIOTERAPIA", "AKM", "KINESIO", "RETIRAR VIA",
        "COLOCACION DE VIA CENTRAL", "VENOCLISIS CENTRAL",
    ],
    # 📋 Valoraciones clínicas importantes (NO agrupar)
    "valoracion_clinica": [
        "VALORACION NEUROLOGICA", "ESCALA DE GLASGOW", "ESCALA DE MORSE",
        "ESCALA DE BRADEN", "ESCALA DE RASS", "ESCALA DE COMA",
    ],
    # 📊 Control/valoración rutinaria (agrupable)
    "control": [
        "SIGNOS VITALES", "CONTROL DE", "FRECUENCIA CARDIACA", 
        "FRECUENCIA RESPIRATORIA", "TENSION ARTERIAL", "TEMPERATURA",
        "SATURACION", "DIURESIS", "GOTEO", "GLUCEMIA", "PESO -",
        "TALLA -", "MONITOREO", "BALANCE HIDRICO", "PESO DE PAÑALES",
    ],
    # 🧹 Higiene y confort (agrupable)
    "higiene": [
        "BAÑO", "HIGIENE", "CAMBIO DE PAÑAL", "CAMBIO DE ROPA", 
        "CAMBIO PARCIAL", "CAMBIO COMPLETO", "LAVADO", "ASEO",
        "CREMA", "EMULSION", "HIDRATANTE", "FAJA ELASTICA",
    ],
    # 🩺 Enfermería general (agrupable)
    "enfermeria": [
        "PULSERA", "TRASLADO", "CABECERA", "BARANDAS", "POSICION",
        "DECUBITO", "ALMOHADA", "MIEMBROS EN ELEVACION", "ORDEN DE LA UNIDAD",
        "CHATA", "ORINAL", "AYUNO", "INFORMACION AL PACIENTE", "ARREGLO",
        "AUSCULTACION", "ALTA - CONFIRMACION", "DEAMBULACION", "CONTENCION",
        "SUEÑO", "REPOSO", "INGRESO - RECIBIMIENTO", "PASE DE TURNO",
        "CONFECCION", "REPORT", "ENTREVISTA", "OBSERVACION DEL PTE",
        "AVISO AL MEDICO", "PLAN DE HIDRATACION", "PERMEABILIDAD",
        "CAMBIO DE PERFUS", "GUIAS DE SUERO", "PARALELO", "RIESGOS AMBIENTALES",
        "ACCESO VENOSO", "VENOCLISIS", "AVP", "AVC", "LIQUIDOS POR BOCA",
        "ENFERMERIA - ECG", "CONFORT", "FRIO / HIELO", "HIELO - APLICACION",
        "COLCHON DE AIRE", "ANTIESCARAS", "VNI INTERMITENTE", "REGISTROS",
        "COMIDA", "ALMUERZO", "CENA", "DESAYUNO", "MERIENDA",
    ],
    # 📝 Valoración de enfermería (agrupable)
    "valoracion": [
        "VALORACION ABDOMINAL", "VALORACION DE DOLOR", "VALORACION DE AVP",
        "VALORACION DE SIGNO", "VALORACION DE FUERZA", "VALORACION DE RESPUESTA",
        "VALORACION DEL SITIO", "VALORACION FISICA", "VALORACION NIVEL",
        "VALORACION DE RIESGO DE UPP", "VALORACION DE RIESGO DE CAIDAS",
        "ESCALA CPOT", "ESCALA MADDOX", "ESCALA DE MADDOX",
        "TOLERANCIA ORAL", "ELIMINACION INTESTINAL", "VALORACION PUPILAR",
        "VALORACION DEL FLUIDO", "VALORACION PULMONAR",
    ],
    # 💊 Administración de medicación (agrupable)
    "medicacion_admin": [
        "ADMINISTRACION DE MEDICACION", "ADMINISTRACION MEDICACION",
        "MEDICACION EV", "MEDICACION VO", "MEDICACION SC", "MEDICACION IM",
        "EN BOLO", "PROTOCOLO",
    ],
}

# Emojis por categoría
CATEGORY_EMOJI = {
    "laboratorio": "🔬",
    "imagen": "📷",
    "estudio": "🔍",
    "interconsulta": "👨‍⚕️",
    "quirurgico": "⚕️",
    "tratamiento": "💉",
    "valoracion_clinica": "📋",
    "control": "📊",
    "higiene": "🧹",
    "enfermeria": "🩺",
    "valoracion": "📝",
    "medicacion_admin": "💊",
    "otro": "•",
}

# Nombres legibles por categoría
CATEGORY_NAMES = {
    "laboratorio": "Laboratorio",
    "imagen": "Estudios por Imágenes",
    "estudio": "Estudios Diagnósticos",
    "interconsulta": "Interconsulta",
    "quirurgico": "Procedimiento",
    "tratamiento": "Tratamiento",
    "valoracion_clinica": "Valoración Clínica",
    "control": "Controles",
    "higiene": "Cuidados",
    "enfermeria": "Enfermería",
    "valoracion": "Valoraciones",
    "medicacion_admin": "Administración Medicación",
    "otro": "Otro",
}


def categorize_procedure(descripcion: str) -> str:
    """
    Categoriza un procedimiento según su descripción.
    Retorna la categoría como string.
    """
    desc_upper = descripcion.upper()
    
    for categoria, keywords in PROCEDURE_CATEGORIES.items():
        for kw in keywords:
            if kw in desc_upper:
                return categoria
    
    return "otro"


def _parse_interconsulta_date(ic: Dict[str, Any]) -> datetime:
    """Parsea fecha de interconsulta para ordenamiento."""
    try:
        return datetime.strptime(ic.get('fecha', ''), "%d/%m/%Y")
    except:
        return datetime.max


def extract_previous_medications_from_text(texto: str) -> List[Dict[str, Any]]:
    """
    Extrae medicación previa/habitual del texto de evolución.
    Busca patrones como:
    - MEDICACION : OXCABAZEPINA 200, CARBAMAZEPINA 200, ...
    - MH: Valsartán 80mg, Levotiroxina 100mcg, ...
    """
    medications = []
    seen = set()
    
    # Patrón 1: "MEDICACION :" o "MEDICACION:"
    med_pattern = r'MEDICACI[OÓ]N\s*:\s*([^\.]+?)(?:\.|ANTECEDENTES|$)'
    match = re.search(med_pattern, texto.upper())
    if match:
        meds_text = match.group(1)
        # Separar por comas
        for med_str in re.split(r'\s*,\s*', meds_text):
            med_str = med_str.strip()
            if not med_str or len(med_str) < 3:
                continue
            
            # Extraer nombre y dosis
            parts = re.match(r'([A-ZÁÉÍÓÚÑ\s\+]+)\s*([\d,\.]+)?\s*(\w+)?', med_str)
            if parts:
                nombre = parts.group(1).strip()
                dosis = (parts.group(2) or "") + " " + (parts.group(3) or "")
                dosis = dosis.strip()
                
                if nombre and nombre.upper() not in seen:
                    seen.add(nombre.upper())
                    medications.append({
                        "tipo": "previa",
                        "farmaco": nombre.title(),
                        "dosis": dosis.lower() if dosis else "",
                        "via": "Oral",
                        "frecuencia": "",
                    })
    
    # Patrón 2: "MH:" (Medicación Habitual)
    mh_pattern = r'MH\s*:\s*(.+?)(?:\n\n|\</|INTERNACION|$)'
    match2 = re.search(mh_pattern, texto, re.IGNORECASE | re.DOTALL)
    if match2:
        mh_text = match2.group(1)
        # Buscar patrones "Nombre dosis/frecuencia"
        for item in re.split(r'\s*-\s*', mh_text):
            item = item.strip()
            if not item or len(item) < 3:
                continue
            
            # Limpiar HTML
            item = re.sub(r'<[^>]+>', '', item)
            
            # Extraer medicamento y dosis
            parts = re.match(r'([A-Za-záéíóúñÁÉÍÓÚÑ/\s]+)\s*([\d,\.]+)?\s*(\w+)?', item)
            if parts:
                nombre = parts.group(1).strip()
                dosis = (parts.group(2) or "") + " " + (parts.group(3) or "")
                
                if nombre and len(nombre) > 2 and nombre.upper() not in seen:
                    seen.add(nombre.upper())
                    medications.append({
                        "tipo": "previa",
                        "farmaco": nombre.strip(),
                        "dosis": dosis.strip().lower() if dosis else "",
                        "via": "Oral",
                        "frecuencia": "",
                    })
    
    return medications



def clean_html_text(text: str) -> str:
    """Limpia entidades HTML y normaliza espacios en blanco."""
    if not text:
        return text
    # Decodificar entidades HTML (&nbsp; -> espacio, etc.)
    cleaned = html.unescape(text)
    # Normalizar múltiples espacios a uno solo
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned.strip()


def _limpiar_motivo(motivo: str) -> str:
    """
    REGLA DE ORO: Motivo de internación = EXACTAMENTE lo que está en la HCE.
    
    Solo limpia HTML tags y espacios. NO modifica el contenido médico.
    """
    if not motivo:
        return "No especificado en HCE"
    
    motivo = motivo.strip()
    
    # Solo limpiar tags HTML y entidades
    motivo = re.sub(r"<[^>]+>", "", motivo).strip()
    motivo = html.unescape(motivo) if motivo else motivo
    
    # Normalizar espacios
    motivo = re.sub(r'\s+', ' ', motivo).strip()
    
    if not motivo or len(motivo) < 3:
        return "No especificado en HCE"
    
    return motivo


def parse_hce_json(hce_doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parsea un documento HCE de MongoDB y extrae datos estructurados.
    
    Args:
        hce_doc: Documento HCE de MongoDB con estructura ainstein
        
    Returns:
        Dict con: medicacion, procedimientos, interconsultas, 
                  diagnosticos, evoluciones, motivo_internacion, paciente_info
    """
    result = {
        "medicacion": [],
        "procedimientos": [],
        "interconsultas": [],
        "diagnosticos": [],
        "evoluciones": [],
        "motivo_internacion": "",
        "parte_quirurgico": "",
        "antecedentes": "",
        "tratamiento_alta": "",
        "plan_seguimiento": "",
        "paciente_edad": None,
        "paciente_sexo": "",
    }
    
    # Intentar extraer de estructura ainstein
    ainstein = hce_doc.get("ainstein", {})
    historia = ainstein.get("historia", [])
    
    # Extraer info del paciente del episodio
    episodio = ainstein.get("episodio", {})
    result["paciente_edad"] = episodio.get("paciEdad")
    sexo_raw = episodio.get("paciSexo", "")
    if sexo_raw == "M":
        result["paciente_sexo"] = "masculino"
    elif sexo_raw == "F":
        result["paciente_sexo"] = "femenino"
    else:
        result["paciente_sexo"] = sexo_raw
    
    if not historia:
        log.warning("[HCEJsonParser] No se encontró ainstein.historia")
        return result
    
    log.info(f"[HCEJsonParser] Procesando {len(historia)} registros de historia")
    
    seen_meds = set()
    seen_procs = set()
    seen_diags = set()
    
    for entry in historia:
        tipo_registro = entry.get("entrTipoRegistro", "")
        fecha = entry.get("entrFechaAtencion", "")
        
        # =====================================================================
        # 0. Motivo: NO usar entrMotivoConsulta ni evolución como fuente.
        # El motivo SOLO se extrae de plantillas con campo "Motivo de Internación"
        # o "Motivo de Ingreso" (ver sección 6: Procesar PLANTILLAS).
        # =====================================================================
        
        # Parsear fecha
        fecha_str = ""
        if fecha:
            try:
                dt = datetime.fromisoformat(fecha.replace("Z", "+00:00"))
                fecha_str = dt.strftime("%d/%m/%Y")
            except:
                fecha_str = str(fecha)[:16]
        
        # 1. Extraer MEDICACIÓN
        meds = entry.get("indicacionFarmacologica", []) or []
        for med in meds:
            farmaco = med.get("geneDescripcion", "").strip()
            if not farmaco:
                continue
            
            # Limpiar nombre (quitar punto inicial)
            if farmaco.startswith("."):
                farmaco = farmaco[1:]
            
            # Excluir soluciones de hidratación
            if any(sol in farmaco.upper() for sol in ["SOLUCION", "DEXTROSA", "FISIOLOGICA", "RINGER"]):
                continue
            
            # Crear clave única para deduplicar
            key = farmaco.upper()
            if key in seen_meds:
                continue
            seen_meds.add(key)
            
            dosis = med.get("enmeDosis", "")
            unidad = med.get("tumeDescripcion", "")
            via = med.get("meviDescripcion", "")
            frecuencia = med.get("mefrDescripcion", "")
            
            result["medicacion"].append({
                "tipo": "internacion",
                "farmaco": farmaco,
                "dosis": f"{dosis} {unidad}".strip() if dosis else "",
                "via": via or "",
                "frecuencia": frecuencia or "",
            })
        
        # 2. Extraer PROCEDIMIENTOS con categorización
        procs = entry.get("indicacionProcedimientos", []) or []
        for proc in procs:
            descripcion = proc.get("procDescripcion", "").strip()
            if not descripcion:
                continue
            
            desc_upper = descripcion.upper()
            
            # Categorizar procedimiento
            categoria = categorize_procedure(descripcion)
            
            # Determinar si es agrupable (rutina de enfermería)
            is_groupable = categoria in ["enfermeria", "control", "valoracion", "higiene", "medicacion_admin"]
            
            obs = proc.get("enprObservacion", "") or ""
            
            # Si el procedimiento es una INTERCONSULTA, agregarlo también a interconsultas
            desc_upper = descripcion.upper()
            if "INTERCONSULTA" in desc_upper:
                # Detectar especialidad de la descripción
                especialidad = "Clínica Médica"  # Por defecto
                desc_lower = descripcion.lower()
                if "cardiolog" in desc_lower:
                    especialidad = "Cardiología"
                elif "neurolog" in desc_lower:
                    especialidad = "Neurología"
                elif "nefrolog" in desc_lower:
                    especialidad = "Nefrología"
                elif "cirugia" in desc_lower or "quirurgic" in desc_lower:
                    especialidad = "Cirugía General"
                elif "traumatolog" in desc_lower or "ortoped" in desc_lower:
                    especialidad = "Traumatología"
                elif "hematolog" in desc_lower:
                    especialidad = "Hematología"
                elif "infectolog" in desc_lower:
                    especialidad = "Infectología"
                elif "neumolog" in desc_lower:
                    especialidad = "Neumonología"
                elif "kinesiol" in desc_lower or "kine" in desc_lower or "fisiatra" in desc_lower:
                    especialidad = "Kinesiología"
                elif "gastroenter" in desc_lower:
                    especialidad = "Gastroenterología"
                elif "endocrino" in desc_lower:
                    especialidad = "Endocrinología"
                elif "urologo" in desc_lower or "urolog" in desc_lower:
                    especialidad = "Urología"
                elif "otorrino" in desc_lower or "orl" in desc_lower:
                    especialidad = "Otorrinolaringología"
                elif "dermato" in desc_lower:
                    especialidad = "Dermatología"
                elif "psiquiat" in desc_lower:
                    especialidad = "Psiquiatría"
                elif "psicolog" in desc_lower:
                    especialidad = "Psicología"
                elif "nutricion" in desc_lower or "nutriolog" in desc_lower:
                    especialidad = "Nutrición"
                elif "paliativ" in desc_lower:
                    especialidad = "Cuidados Paliativos"
                else:
                    # Intentar extraer especialidad del nombre del procedimiento
                    # Ej: "INTERCONSULTA A INFECTOLOGIA" -> "Infectología"
                    match = re.search(r'INTERCONSULTA\s+(?:A\s+)?(\w+)', descripcion, re.IGNORECASE)
                    if match:
                        especialidad = match.group(1).capitalize()
                
                result["interconsultas"].append({
                    "fecha": fecha_str,
                    "especialidad": especialidad,
                    "observacion": obs or descripcion,
                })
            
            result["procedimientos"].append({
                "fecha": fecha_str,
                "descripcion": descripcion,
                "observacion": obs,
                "categoria": categoria,
                "agrupable": is_groupable,
            })
        
        # 3. Extraer DIAGNÓSTICOS
        diags = entry.get("diagnosticos", []) or []
        for diag in diags:
            desc = diag.get("diagDescripcion", "").strip()
            if desc and desc not in seen_diags:
                seen_diags.add(desc)
                result["diagnosticos"].append(desc)
        
        # 4. Extraer EVOLUCIONES — REGLA DE ORO: SOLO EVOLUCIÓN MÉDICA
        # Descartamos enfermería, interconsultas (tienen sección propia),
        # controles, balances, y cualquier otro tipo no médico.
        TIPOS_EVOLUCION_VALIDOS = {
            "EVOLUCION MEDICA (A CARGO)",
            "INGRESO DE PACIENTE",
            "PARTE QUIRURGICO",
            "PARTE PROCEDIMIENTO",
        }
        evolucion = entry.get("entrEvolucion", "")
        if evolucion:
            # Limpiar entidades HTML
            evolucion = clean_html_text(evolucion)
        if evolucion and len(evolucion) > 50 and tipo_registro in TIPOS_EVOLUCION_VALIDOS:
            result["evoluciones"].append({
                "tipo": tipo_registro,
                "fecha": fecha_str,
                "texto": evolucion,
            })
        
        # 4b. Si es EVOLUCION DE INTERCONSULTA, extraer como interconsulta
        if tipo_registro == "EVOLUCION DE INTERCONSULTA" and evolucion:
            # Intentar detectar especialidad del texto
            especialidad = "Clínica Médica"  # Por defecto
            evol_lower = evolucion.lower()
            if "cardiolog" in evol_lower:
                especialidad = "Cardiología"
            elif "neurolog" in evol_lower:
                especialidad = "Neurología"
            elif "nefrolog" in evol_lower:
                especialidad = "Nefrología"
            elif "cirugia" in evol_lower or "quirurgic" in evol_lower:
                especialidad = "Cirugía General"
            elif "traumatolog" in evol_lower or "ortoped" in evol_lower:
                especialidad = "Traumatología"
            elif "hematolog" in evol_lower:
                especialidad = "Hematología"
            elif "infectolog" in evol_lower:
                especialidad = "Infectología"
            elif "neumolog" in evol_lower:
                especialidad = "Neumonología"
            elif "kinesiol" in evol_lower or "kine" in evol_lower:
                especialidad = "Kinesiología"
            
            # GUARDAR LA EVOLUCIÓN COMPLETA - el resumen se hace después al formatear
            result["interconsultas"].append({
                "fecha": fecha_str,
                "especialidad": especialidad,
                "observacion": evolucion,  # Guardar completa, no cortada
            })
        
        # 5. Procesar PARTE QUIRÚRGICO
        if tipo_registro == "PARTE QUIRURGICO":
            result["parte_quirurgico"] = evolucion or ""
        
        # 6. Procesar PLANTILLAS (Anamnesis, Resumen Internacion, etc.)
        # ⛔ EXCLUIR EPICRISIS: el usuario pide que NO se use esta sección
        plantillas = entry.get("plantillas", []) or []
        for plantilla in plantillas:
            grupo = plantilla.get("grupDescripcion", "")
            propiedades = plantilla.get("propiedades", []) or []
            
            # RESUMEN INTERNACION: Máxima prioridad para motivo
            if grupo == "RESUMEN INTERNACION":
                for prop in propiedades:
                    nombre = prop.get("grprDescripcion", "")
                    valor = prop.get("engpValor", "") or ""
                    valor = clean_html_text(valor) if valor else ""
                    
                    nombre_lower = nombre.lower()
                    if "motivo" in nombre_lower and ("internaci" in nombre_lower or "ingreso" in nombre_lower):
                        motivo = re.sub(r"<[^>]+>", "", valor).strip()
                        if motivo:
                            # RESUMEN INTERNACION siempre sobreescribe (máxima prioridad)
                            result["motivo_internacion"] = motivo
                            log.info(f"[HCEJsonParser] Motivo de RESUMEN INTERNACION: {motivo[:80]}")
            
            elif grupo == "ANAMNESIS":
                for prop in propiedades:
                    nombre = prop.get("grprDescripcion", "")
                    valor = prop.get("engpValor", "") or ""
                    
                    # Limpiar HTML entities PRIMERO
                    valor = clean_html_text(valor) if valor else ""
                    
                    nombre_lower = nombre.lower()
                    if "motivo" in nombre_lower and ("internaci" in nombre_lower or "ingreso" in nombre_lower) and not result["motivo_internacion"]:
                        # Solo si no hay motivo aún (RESUMEN INTERNACION tiene prioridad)
                        motivo = re.sub(r"<[^>]+>", "", valor).strip()
                        if motivo:
                            result["motivo_internacion"] = motivo
                    
                    if "Antecedentes" in nombre:
                        # Guardar antecedentes limpios
                        result["antecedentes"] = re.sub(r"<[^>]+>", "", valor).strip()
                        
                        # Extraer medicación habitual si existe
                        if "medicación habitual" in valor.lower() or "mh:" in valor.lower():
                            # Buscar el texto después de "medicación habitual" o "MH:"
                            match = re.search(r"(?:medicación habitual:?|mh:)\s*([^.]+)", valor, re.I)
                            if match:
                                meds_text = match.group(1).strip()
                                # Parsear medicamentos (pueden estar separados por comas, /, "y")
                                for med_raw in re.split(r"[,/]|\sy\s", meds_text):
                                    med = med_raw.strip()
                                    if med and len(med) > 2:
                                        # Agregar como medicación previa
                                        result["medicacion"].append({
                                            "tipo": "previa",
                                            "descripcion": med,
                                            "dosis": "",
                                            "via": "",
                                            "frecuencia": "",
                                        })
            
            # ⛔ EPICRISIS EXCLUIDA: no extraer motivo de esta sección
            # (solo tratamiento al alta y plan de seguimiento si existen)
            elif grupo == "EPICRISIS":
                for prop in propiedades:
                    nombre = prop.get("grprDescripcion", "")
                    valor = prop.get("engpValor", "") or ""
                    valor = clean_html_text(valor) if valor else ""
                    
                    if "Tratamiento al alta" in nombre:
                        result["tratamiento_alta"] = re.sub(r"<[^>]+>", "", valor).strip()
                    if "Plan de seguimiento" in nombre:
                        result["plan_seguimiento"] = re.sub(r"<[^>]+>", "", valor).strip()
            
            # Cualquier otra plantilla: buscar campo "Motivo" (case-insensitive)
            else:
                if not result["motivo_internacion"]:
                    for prop in propiedades:
                        nombre = prop.get("grprDescripcion", "")
                        valor = prop.get("engpValor", "") or ""
                        nombre_lower = nombre.lower()
                        # Buscar campo que diga "motivo" + alguna variante
                        if "motivo" in nombre_lower and any(x in nombre_lower for x in ["internaci", "ingreso", "consulta"]):
                            valor = clean_html_text(valor) if valor else ""
                            motivo = re.sub(r"<[^>]+>", "", valor).strip()
                            if motivo and len(motivo) > 3:
                                result["motivo_internacion"] = motivo
                                log.info(f"[HCEJsonParser] Motivo de plantilla [{grupo}]: {motivo[:80]}")
    
    # 7. Extraer medicación PREVIA del texto de evoluciones
    # TODO: DESHABILITADO - el parser está extrayendo basura
    # seen_prev = set(m.get("farmaco", "").upper() for m in result["medicacion"])
    # for evol in result["evoluciones"]:
    #     texto = evol.get("texto", "")
    #     if texto:
    #         prev_meds = extract_previous_medications_from_text(texto)
    #         for med in prev_meds:
    #             if med["farmaco"].upper() not in seen_prev:
    #                 seen_prev.add(med["farmaco"].upper())
    #                 result["medicacion"].append(med)
    
    # 8. Motivo: NO usar evolución como fallback.
    # El motivo SOLO viene de plantillas explícitas (Motivo de Internación/Ingreso).
    # Si ninguna plantilla lo tiene, queda como "No especificado en HCE".
    
    # 9. REGLA DE ORO: Limpiar y normalizar motivo de internación
    result["motivo_internacion"] = _limpiar_motivo(result["motivo_internacion"])
    
    log.info(f"[HCEJsonParser] Extraído: meds={len(result['medicacion'])}, "
             f"procs={len(result['procedimientos'])}, diags={len(result['diagnosticos'])}")
    
    return result


def extract_medications_from_json(hce_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extrae solo medicación del documento HCE JSON."""
    parsed = parse_hce_json(hce_doc)
    return parsed.get("medicacion", [])


def extract_procedures_from_json(hce_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extrae solo procedimientos del documento HCE JSON."""
    parsed = parse_hce_json(hce_doc)
    return parsed.get("procedimientos", [])


def sort_medications_alphabetically(medications: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ordena medicamentos alfabéticamente por nombre de fármaco."""
    # Separar por tipo
    internacion = [m for m in medications if m.get("tipo") == "internacion"]
    previa = [m for m in medications if m.get("tipo") == "previa"]
    
    # Ordenar cada grupo alfabéticamente
    internacion.sort(key=lambda m: (m.get("farmaco") or "").lower())
    previa.sort(key=lambda m: (m.get("farmaco") or "").lower())
    
    return internacion + previa

def sort_and_group_procedures(
    procedures: List[Dict[str, Any]],
    excluded_sections: Optional[List[str]] = None,
) -> List[str]:
    """
    Filtra y ordena procedimientos para mostrar SOLO los clínicamente relevantes.
    
    Se MUESTRAN individualmente:
    - Cirugías y procedimientos invasivos
    - Estudios diagnósticos importantes
    - Imágenes (RX, ECO, TAC, RMN)
    
    Se AGRUPAN (resumen):
    - Laboratorios -> "Laboratorios realizados (N estudios)"
    - AKM/Kinesio -> "Asistencia kinésica motora durante la internación"
    
    Se OCULTAN completamente:
    - Procedimientos de ingreso genéricos
    - Rutina de enfermería
    - Controles y valoraciones
    - Interconsultas (tienen su propia sección)
    """
    from collections import defaultdict
    
    # =========================================================================
    # LISTA NEGRA EXTENSA DE PROCEDIMIENTOS GENÉRICOS A OCULTAR
    # Según REGLAS_GENERACION_EPC.md: NO son procedimientos invasivos/intervencionistas
    # =========================================================================
    GENERIC_PROCEDURES_BLACKLIST = [
        # Administrativo / Ingreso
        "RECEPCION Y TOMA DE MUESTRA",
        "MATERIAL DESCARTABLE",
        "INTERNACION GENERAL",
        "INTERNACION SIN AISLAMIENTO",
        "INTERNACION UCI", "INTERNACION UTI",
        "INGRESO",
        
        # Cuidados post-mortem
        "CUIDADOS POSTMORTEN", "CUIDADOS POST MORTEM", "CUIDADOS POSTMORTEM",
        
        # Alimentación (rutinario)
        "ALIMENTACION ENTERAL",
        
        # Rutinas de enfermería - NO SON PROCEDIMIENTOS
        "SONDA NASOGASTRICA",
        "ASPIRACION SECRECIONES", "ASPIRACION DE SECRECIONES",
        "DRENAJE - CONTROL", "DRENAJE CONTROL", "CONTROL Y MEDICION",
        "SUJECION DEL TUBO", "SUJECION DE TUBO", "FIJACION DEL TUBO",
        "HIGIENE", "HIGIENE CONFORT", "BAÑO EN CAMA",
        "CAMBIO DE POSICION", "MOVILIZACION PASIVA",
        "CURACION PLANA", "CURACION SIMPLE",
        "CAMBIO DE PAÑAL", "CONTROL DE DEPOSICIONES",
        "CONTROL DEL DOLOR", "ESCALA DE DOLOR",
        "MEDICION DE DIURESIS", "BALANCE HIDRICO",
        
        # Controles genéricos - NO SON PROCEDIMIENTOS
        "CONTROL DE", "SIGNOS VITALES", "SATURACION", "TEMPERATURA",
        "FRECUENCIA CARDIACA", "FRECUENCIA RESPIRATORIA",
        "TENSION ARTERIAL", "PRESION ARTERIAL",
        "VALORACION INICIAL", "VALORACION DE ENFERMERIA",
        "MONITOREO CONTINUO", "MONITOREO CARDIACO",
        
        # Observación/Conductas - van en Evolución, no en Procedimientos
        "OBSERVACION", "CONTROL EVOLUTIVO", "SEGUIMIENTO",
        "EVALUACION CLINICA", "VALORACION CLINICA",
    ]
    
    # Keywords para identificar laboratorios (se agrupan)
    LAB_KEYWORDS = [
        "LABORATORIO", "HEMOGRAMA", "PLAQUETAS", "COAGULACION",
        "TROMBOPLASTINA", "PROTROMBINA", "ORINA COMPLETA",
        "ERITROSEDIMENTACION", "HEMOGLOBINA GLICOSILADA", "HB A1C",
        "PROTEINOGRAMA", "ACIDO FOLICO", "FERREMIA", "RETICULOCITOS",
        "CEA", "CA 19-9", "CAPACIDAD TOTAL DE FIJACION", "ANTICUERPO",
        "ANTITIROGLOBULINA", "ATPO-ANTIPEROXIDASA", "PRO BNP",
        "PARATHORMONA", "VIT D", "25-OH-VIT", "IONOGRAMA", "GASOMETRIA",
        "GLUCEMIA", "UREMIA", "CREATININA", "HEPATOGRAMA", "GOT", "GPT",
        "BILIRRUBINA", "ALBUMINA", "PROTEINAS TOTALES", "CULTIVO",
        "HEMOCULTIVO", "UROCULTIVO", "COPROCULTIVO",
    ]
    
    # Categorías que se OCULTAN completamente (no mostrar ni agrupar)
    # Si se pasan excluded_sections, usar esas; sino usar defaults
    default_hidden = {
        "control", "higiene", "enfermeria", 
        "valoracion", "medicacion_admin", "valoracion_clinica",
        "interconsulta",  # Ya están en su sección
    }
    hidden_categories = set(excluded_sections) if excluded_sections else default_hidden
    
    def parse_date(p):
        fecha = p.get("fecha", "")
        try:
            return datetime.strptime(fecha, "%d/%m/%Y")
        except:
            return datetime.max
    
    def is_lab_procedure(descripcion: str) -> bool:
        """Determina si es un procedimiento de laboratorio."""
        desc_upper = descripcion.upper()
        return any(kw in desc_upper for kw in LAB_KEYWORDS)
    
    def is_blacklisted(descripcion: str) -> bool:
        """Verifica si está en lista negra de genéricos."""
        desc_upper = descripcion.upper()
        return any(bl in desc_upper for bl in GENERIC_PROCEDURES_BLACKLIST)
    
    # Contadores para agrupación
    lab_count = 0
    lab_items = []  # Guardar laboratorios individuales para enviar al frontend
    akm_count = 0
    
    # Procedimientos importantes individuales
    important_procs = []
    
    for p in procedures:
        categoria = p.get("categoria", "otro")
        descripcion = p.get("descripcion", "")
        fecha = p.get("fecha", "")
        desc_upper = descripcion.upper()
        
        # 1. Verificar si es laboratorio - AGRUPAR, no mostrar individualmente
        if categoria == "laboratorio" or is_lab_procedure(descripcion):
            lab_count += 1
            if fecha and descripcion:
                lab_items.append(f"{fecha} - {descripcion}")
            elif descripcion:
                lab_items.append(descripcion)
            continue  # No agregar individualmente en procedimientos, se agrupa al final
        
        # 2. Verificar si está en lista negra de genéricos
        if is_blacklisted(descripcion):
            continue
        
        # 3. Ocultar categorías rutinarias de enfermería
        if categoria in hidden_categories:
            continue
        
        # 4. Contar AKM/Kinesio (agrupar)
        if "AKM" in desc_upper or "KINESIC" in desc_upper or "KINESIO" in desc_upper:
            akm_count += 1
            continue
        
        # 4b. EXCLUIR estudios de imagen (van en sección "Estudios" separada)
        STUDY_KEYWORDS = [
            "RX ", "RADIOGRAFIA", "TAC ", "TOMOGRAFIA", "RMN ", "RESONANCIA",
            "ECOGRAFIA", "ECOCARDIOGRAMA", "CENTELLOGRAMA", "SPECT",
            "MAMOGRAFIA", "DENSITOMETRIA", "DOPPLER", "ECODOPLER", "ECODOPPLER",
            "VEDA ", "VCC", "ENDOSCOPIA DIGESTIVA", "COLONOSCOPIA", "BRONCOSCOPIA",
            "ELECTROCARDIOGRAMA", "ECG", "HOLTER", "ERGOMETRIA",
        ]
        is_study = any(kw in desc_upper for kw in STUDY_KEYWORDS)
        # Solo excluir si NO es biopsia/punción (esos son procedimientos)
        is_invasive = any(kw in desc_upper for kw in ["BIOPSIA", "PUNCION", "COLOCACION", "CATETERISMO"])
        if is_study and not is_invasive:
            continue  # Este estudio va en la sección "Estudios"
        
        # 5. Más keywords a ocultar (rutina que no entra en categorías)
        skip_keywords = [
            "OBSERVACION", "SUEÑO", "REPOSO", "PASE DE", 
            "REGISTROS", "CONFECCION", "ARREGLO", "ORDEN DE",
            "INFORMACION AL", "ENTREVISTA", "AVISO",
            "RETIRAR VIA", "PERMEABILIDAD", "ACCESO VENOSO",
            "VALORACION DLEE", "VALORACION DE", "VALORACION DEL",
            "PULSERA", "TRASLADO", "CABECERA", "BARANDAS",
            "DECUBITO", "ALMOHADA", "CHATA", "ORINAL",
            "INTERCONSULTA",  # Las interconsultas van en su sección propia
        ]
        
        should_skip = any(kw in desc_upper for kw in skip_keywords)
        if should_skip:
            continue
        
        # 6. Filtrar nombres incompletos ("CIRUGIA POR", "TRATAMIENTO DE")
        if _is_incomplete_procedure(descripcion):
            continue
        
        # ¡Este procedimiento es importante! Agregarlo
        important_procs.append(p)
    
    # Ordenar cronológicamente
    important_procs.sort(key=parse_date)
    
    # NUEVO: Agrupar procedimientos por nombre, acumular fechas
    from collections import OrderedDict
    procs_por_nombre: OrderedDict = OrderedDict()
    
    for p in important_procs:
        fecha = p.get("fecha", "")
        descripcion = p.get("descripcion", "")
        desc_key = descripcion.upper().strip()
        
        if desc_key not in procs_por_nombre:
            procs_por_nombre[desc_key] = {
                "nombre": descripcion,
                "fechas": [],
            }
        if fecha and fecha not in procs_por_nombre[desc_key]["fechas"]:
            procs_por_nombre[desc_key]["fechas"].append(fecha)
    
    result = []
    for desc_key, info in procs_por_nombre.items():
        nombre = info["nombre"]
        fechas = info["fechas"]
        
        # Formato: "Nombre (fecha1, fecha2)" o solo "Nombre" si no hay fechas
        nombre_fmt = _medical_title_case(nombre)
        if fechas:
            # Ordenar fechas cronológicamente
            try:
                fechas_sorted = sorted(fechas, key=lambda f: datetime.strptime(f, "%d/%m/%Y"))
            except:
                fechas_sorted = fechas
            fechas_str = ", ".join(fechas_sorted)
            result.append(f"{nombre_fmt} ({fechas_str})")
        else:
            result.append(nombre_fmt)
    
    # Agregar AKM agrupado al final si hubo
    if akm_count > 0:
        result.append(f"Asistencia kinésica motora durante la internación ({akm_count} sesiones)")
    
    print(f"[PostProcess] Procedimientos finales: {len(result)} items")
    for i, item in enumerate(result[:5]):
        print(f"  [{i}] {item[:80]}...")
    
    return result


def sort_procedures_chronologically(
    procedures: List[Dict[str, Any]],
    excluded_sections: Optional[List[str]] = None,
) -> List[str]:
    """Alias para compatibilidad - usa la nueva función de agrupación."""
    return sort_and_group_procedures(procedures, excluded_sections)


def extract_lab_procedures(
    procedures: List[Dict[str, Any]],
) -> List[str]:
    """
    Extrae LABORATORIOS individuales de los procedimientos.
    
    Estos laboratorios normalmente se agrupan en un solo item para la sección
    de procedimientos, pero el frontend necesita acceso a la lista completa
    para mostrar en el modal de "Otros Datos de Interés".
    
    Returns:
        Lista de strings en formato "DD/MM/YYYY HH:MM - DESCRIPCION"
    """
    LAB_KEYWORDS = [
        "LABORATORIO", "HEMOGRAMA", "GLUCEMIA", "CREATININA", "UREMIA", 
        "IONOGRAMA", "HEPATOGRAMA", "COAGULOGRAMA", "CALCEMIA", "MAGNESIO",
        "LACTICO", "LÁCTICO", "LDH", "FOSFATEMIA", "ACIDO BASE", "ÁCIDO BASE",
        "GASOMETRIA", "GASOMETRÍA", "COLESTEROL", "TRIGLICERIDOS", "TRIGLICÉRIDOS",
        "URICEMIA", "BILIRRUBINA", "PROTEINAS", "PROTEÍNAS", "ALBUMINA", "ALBÚMINA",
        "AMILASA", "LIPASA", "PCR", "VSG", "ERITROSEDIMENTACION", "ERITROSEDIMENTACIÓN",
        "FERRITINA", "TRANSFERRINA", "VITAMINA", "HORMONAS", "TSH", "T3", "T4",
        "HISOPADO", "HEMOCULTIVO", "UROCULTIVO", "COPROCULTIVO", "CULTIVO",
        "CALCIO IONICO", "CALCIO IÓNICO", "FOSFORO", "FÓSFORO",
        "POTASIO", "SODIO", "CLORO", "BICARBONATO", "UREA",
        "TRANSAMINASAS", "GOT", "GPT", "FOSFATASA", "GGT", "GAMMA GT",
        "TIEMPO DE PROTROMBINA", "TPPA", "DIMERO D", "FIBRINOGENO", "FIBRINÓGENO",
    ]
    
    def is_lab(descripcion: str) -> bool:
        desc_upper = descripcion.upper()
        return any(kw in desc_upper for kw in LAB_KEYWORDS)
    
    def parse_date(p):
        fecha = p.get("fecha", "")
        try:
            return datetime.strptime(fecha, "%d/%m/%Y")
        except:
            return datetime.max
    
    # Filtrar solo laboratorios
    labs = [p for p in procedures if p.get("categoria") == "laboratorio" or is_lab(p.get("descripcion", ""))]
    
    # Agrupar por descripción (sin fecha/hora) - solo valores únicos
    seen = set()
    result = []
    for p in labs:
        descripcion = p.get("descripcion", "").strip()
        if descripcion and descripcion.upper() not in seen:
            seen.add(descripcion.upper())
            result.append(descripcion)
    
    # Ordenar alfabéticamente para mejor lectura
    result.sort()
    
    return result


def extract_studies_chronologically(
    procedures: List[Dict[str, Any]],
    excluded_sections: Optional[List[str]] = None,
) -> List[str]:
    """
    Extrae ESTUDIOS DIAGNÓSTICOS agrupados por tipo.
    
    REGLA: Agrupar por tipo de estudio, mostrar solo la primera fecha/hora de cada tipo.
    Ejemplo: Si hay 8 "Tránsito intestinal", solo aparece 1 con la primera fecha.
    
    Usa el módulo estudios_rules.py que define 11 categorías:
    - Diagnóstico por Imágenes (RX, TAC, RMN, Eco, Doppler, etc.)
    - Cardiología (ECG, Holter, CCG, etc.)
    - Neurología (EEG, EMG, etc.)
    - Neumonología (Espirometría, etc.)
    - Endoscopía (VEDA, VCC, etc.)
    - Oftalmología, Traumatología, ORL, Ginecología, Urología, Genética
    
    Returns:
        Lista de strings en formato "DD/MM/YYYY HH:MM - ESTUDIO" (agrupados por tipo)
    """
    from app.services.estudios_rules import clasificar_estudio, es_estudio
    
    # Keywords para EXCLUIR de Estudios (son PROCEDIMIENTOS, no estudios)
    # Según Tabla de Decisión: endoscopías, invasivos/intervencionistas → Procedimientos
    EXCLUDE_KEYWORDS = [
        # Quirúrgicos/Invasivos
        "BIOPSIA", "PUNCION", "COLOCACION", "EXTRACCION", "CIRUGIA",
        "ANGIOPLASTIA", "STENT", "MARCAPASOS", "DRENAJE", "CATETER",
        # Intervencionismos cardíacos
        "ABLACION", "ABLACIÓN",  # ⚠️ Ablación por catéter = procedimiento intervencionista
        "CATETERISMO", "HEMODINAMIA",
        # Accesos/Dispositivos
        "CVC", "VIA CENTRAL", "PICC", "INTUBACION", "IOT",
        # Terapéuticos invasivos
        "TRANSFUSION", "DIALISIS", "CARDIOVERSION", "RCP", "DESFIBRILACION",
    ]
    
    def is_study(descripcion: str) -> bool:
        """Determina si es un estudio diagnóstico usando reglas estándar."""
        desc_upper = descripcion.upper()
        
        # Verificar si tiene keywords de exclusión
        if any(kw in desc_upper for kw in EXCLUDE_KEYWORDS):
            return False
        
        # Usar el clasificador de estudios
        return es_estudio(descripcion)
    
    def parse_date(p):
        fecha = p.get("fecha", "")
        try:
            return datetime.strptime(fecha, "%d/%m/%Y")
        except:
            return datetime.max
    
    # Filtrar solo estudios — excluir laboratorios explícitamente
    studies = [
        p for p in procedures
        if is_study(p.get("descripcion", "")) and not _is_lab_item(p.get("descripcion", ""))
    ]
    
    # Ordenar cronológicamente (para que el primero de cada tipo sea el más antiguo)
    studies.sort(key=parse_date)
    
    # NUEVO: Agrupar estudios por nombre, acumular TODAS las fechas
    from collections import OrderedDict
    estudios_por_tipo: OrderedDict = OrderedDict()
    
    for p in studies:
        fecha = p.get("fecha", "")
        descripcion = p.get("descripcion", "")
        
        # Clasificar el estudio para obtener nombre normalizado
        clasificacion = clasificar_estudio(descripcion)
        if clasificacion:
            nombre_norm = clasificacion["nombre"]
        else:
            nombre_norm = descripcion.strip()
        
        if nombre_norm not in estudios_por_tipo:
            estudios_por_tipo[nombre_norm] = []
        if fecha and fecha not in estudios_por_tipo[nombre_norm]:
            estudios_por_tipo[nombre_norm].append(fecha)
    
    # Construir resultado: "Nombre (fecha1, fecha2)"
    result = []
    for nombre, fechas in estudios_por_tipo.items():
        nombre_fmt = _medical_title_case(nombre)
        if fechas:
            # Ordenar fechas cronológicamente
            try:
                fechas_sorted = sorted(fechas, key=lambda f: datetime.strptime(f, "%d/%m/%Y"))
            except:
                fechas_sorted = fechas
            fechas_str = ", ".join(fechas_sorted)
            result.append(f"{nombre_fmt} ({fechas_str})")
        else:
            result.append(nombre_fmt)
    
    return result




def extract_interconsultas_chronologically(
    interconsultas: List[Dict[str, Any]],
) -> List[str]:
    """
    Formatea INTERCONSULTAS agrupadas por especialidad.
    
    REGLA: Agrupar por especialidad, mostrar solo la primera fecha/hora de cada una.
    Ejemplo: Si hay 3 interconsultas a "Infectología", solo aparece 1 con la primera fecha.
    
    Returns:
        Lista de strings en formato "DD/MM/YYYY HH:MM - Especialidad" (agrupados)
    """
    def parse_date(ic):
        fecha = ic.get("fecha", "")
        try:
            return datetime.strptime(fecha, "%d/%m/%Y")
        except:
            return datetime.max
    
    # Ordenar cronológicamente (para que la primera de cada especialidad sea la más antigua)
    sorted_ic = sorted(interconsultas, key=parse_date)
    
    # Agrupar por especialidad - sin fecha, solo nombre de especialidad
    especialidades_vistas: set = set()
    result = []
    
    for ic in sorted_ic:
        especialidad = ic.get("especialidad", "Clínica Médica").strip()
        
        # Solo una vez por especialidad
        if especialidad not in especialidades_vistas:
            especialidades_vistas.add(especialidad)
            result.append(especialidad)
    
    # Ordenar alfabéticamente
    result.sort()
    
    return result


async def generate_epc_from_json(
    hce_doc: Dict[str, Any],
    patient_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    db: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Genera EPC desde documento HCE JSON estructurado.
    
    Args:
        hce_doc: Documento HCE de MongoDB (con estructura ainstein)
        patient_id: ID del paciente (opcional)
        tenant_id: ID del tenant para aplicar reglas de visualización (opcional)
        db: Sesión de SQLAlchemy para obtener reglas del tenant (opcional)
        
    Returns:
        Dict con estructura EPC completa
    """
    from app.services.ai_gemini_service import GeminiAIService
    from app.services.tenant_rules_service import get_excluded_sections_for_tenant, DEFAULT_EXCLUDED_SECTIONS
    
    log.info("[EPC-JSON] Generando EPC desde JSON estructurado")
    
    # =========================================================================
    # OBTENER REGLAS DE EXCLUSIÓN DEL TENANT
    # =========================================================================
    if db and tenant_id:
        excluded_sections = get_excluded_sections_for_tenant(db, tenant_id)
    else:
        # Usar defaults si no hay db o tenant_id
        excluded_sections = DEFAULT_EXCLUDED_SECTIONS.copy()
    log.info(f"[EPC-JSON] Tenant {tenant_id}: excluyendo secciones {excluded_sections}")
    
    # 1. Parsear documento JSON
    parsed = parse_hce_json(hce_doc)
    
    # =========================================================================
    # DETECCIÓN DE ÓBITO DESDE EPISODIO (taltDescripcion)
    # Aunque las evoluciones no lo mencionen, el alta puede indicar OBITO
    # =========================================================================
    ainstein = hce_doc.get("ainstein", {})
    episodio = ainstein.get("episodio", {})
    tipo_alta = (episodio.get("taltDescripcion") or "").upper()
    es_obito_por_alta = "OBITO" in tipo_alta or "ÓBITO" in tipo_alta or "FALLEC" in tipo_alta
    
    if es_obito_por_alta:
        log.info(f"[EPC-JSON] ⚠️ DETECTADO ÓBITO desde taltDescripcion: {tipo_alta}")
    
    print(f"[EPC-JSON] Medicamentos extraídos: {len(parsed['medicacion'])}")
    print(f"[EPC-JSON] Procedimientos extraídos: {len(parsed['procedimientos'])}")
    print(f"[EPC-JSON] Diagnósticos: {parsed['diagnosticos']}")
    print(f"[EPC-JSON] Motivo internación: {parsed['motivo_internacion']}")
    print(f"[EPC-JSON] Tipo de alta: {tipo_alta} (es_obito: {es_obito_por_alta})")
    print(f"[EPC-JSON] Secciones excluidas por tenant: {excluded_sections}")
    
    # 2. Ordenar medicación alfabéticamente
    sorted_meds = sort_medications_alphabetically(parsed["medicacion"])
    
    # 3. Ordenar y FILTRAR procedimientos según reglas del tenant
    sorted_procs = sort_procedures_chronologically(parsed["procedimientos"], excluded_sections)
    
    # 3b. Extraer ESTUDIOS diagnósticos (TAC, RMN, RX, etc.) - nueva sección
    sorted_studies = extract_studies_chronologically(parsed["procedimientos"], excluded_sections)
    # REGLA DE ORO: Agrupar estudios repetidos por nombre con fechas consolidadas
    sorted_studies = _group_studies_by_name(sorted_studies)
    
    # 3c. Extraer LABORATORIOS individuales para modal "Otros Datos de Interés"
    lab_procedures = extract_lab_procedures(parsed["procedimientos"])
    
    # 3d. Extraer INTERCONSULTAS en orden cronológico
    sorted_interconsultas = extract_interconsultas_chronologically(parsed.get("interconsultas", []))
    
    print(f"[EPC-JSON] Procedimientos después de filtrar: {len(sorted_procs)}")
    print(f"[EPC-JSON] Estudios extraídos: {len(sorted_studies)}")
    print(f"[EPC-JSON] Laboratorios extraídos: {len(lab_procedures)}")
    print(f"[EPC-JSON] Interconsultas extraídas: {len(sorted_interconsultas)}")
    
    # 4. Generar evolución con IA si hay datos
    motivo = parsed["motivo_internacion"]
    evolucion = ""
    
    print(f"[EPC-JSON] Evoluciones encontradas: {len(parsed['evoluciones'])}")
    
    if parsed["evoluciones"]:
        # =====================================================================
        # INCLUIR 100% DE TODAS LAS EVOLUCIONES SIN TRUNCAR
        # El contexto completo es necesario para generar una EPC correcta
        # =====================================================================
        
        evol_texts = []
        for e in parsed["evoluciones"]:
            texto = e.get("texto", "")
            if texto:
                tipo = e.get("tipo", "")
                fecha = e.get("fecha", "")
                # SIN TRUNCAR - incluir texto completo
                evol_texts.append(f"[{tipo}] [{fecha}]\n{texto}")
        
        # TODAS las evoluciones, sin límite
        context = "\n\n---\n\n".join(evol_texts)
        
        # Construir info del paciente
        paciente_info = ""
        if parsed["paciente_edad"] and parsed["paciente_sexo"]:
            paciente_info = f"Paciente de {parsed['paciente_edad']} años, sexo {parsed['paciente_sexo']}"
        elif parsed["paciente_edad"]:
            paciente_info = f"Paciente de {parsed['paciente_edad']} años"
        
        # TODOS los diagnósticos
        todos_diagnosticos = ', '.join(parsed['diagnosticos']) if parsed['diagnosticos'] else 'No especificados'
        
        # TODOS los procedimientos (sin límite)
        todos_procedimientos = ', '.join([p.get('descripcion', '') for p in parsed['procedimientos']]) if parsed['procedimientos'] else 'No registrados'
        
        # Generar evolución con IA
        ai = GeminiAIService()
        
        # Determinar si es óbito desde la fuente de verdad (taltDescripcion)
        tipo_alta_texto = tipo_alta if tipo_alta else "ALTA"
        es_obito_confirmado = es_obito_por_alta
        
        prompt_narrador = f"""Eres un médico especialista redactando la sección EVOLUCIÓN de una epicrisis.

DATOS DEL CASO:
- PACIENTE: {paciente_info if paciente_info else 'No especificado'}
- MOTIVO INTERNACIÓN: {motivo if motivo else 'No especificado'}
- DIAGNÓSTICOS: {todos_diagnosticos}
- PROCEDIMIENTOS REALIZADOS: {todos_procedimientos}
- PARTE QUIRÚRGICO: {parsed['parte_quirurgico'] if parsed['parte_quirurgico'] else 'N/A'}
- TIPO DE ALTA: {tipo_alta_texto}

EVOLUCIONES MÉDICAS REGISTRADAS:
{context}

═══════════════════════════════════════════════════════════════
INSTRUCCIONES DE REDACCIÓN (MÁXIMA PRIORIDAD)
═══════════════════════════════════════════════════════════════

DEBES generar un texto narrativo COMPLETO con la siguiente estructura obligatoria de 3-4 párrafos:

PÁRRAFO 1 - INGRESO Y ANTECEDENTES:
- Comenzar SIEMPRE con "{paciente_info}, " seguido de antecedentes relevantes
- Incluir motivo de internación, comorbilidades, medicación habitual relevante
- Describir el estado al ingreso

PÁRRAFO 2 - EVOLUCIÓN CLÍNICA:
- Narrar cronológicamente la evolución durante la internación
- Incluir hallazgos de estudios realizados (laboratorios, imágenes, etc.)
- Describir interconsultas relevantes y sus conclusiones
- Mencionar procedimientos realizados (sin detallar fármacos específicos)

PÁRRAFO 3 - COMPLICACIONES Y TRATAMIENTO:
- Describir complicaciones si las hubo
- Mencionar cambios en el plan terapéutico (sin nombrar fármacos individuales)
- Incluir respuesta al tratamiento
- Si no hubo complicaciones relevantes, fusionar con párrafo 2

PÁRRAFO FINAL - DESENLACE:
{f'''- El paciente FALLECIÓ durante la internación (tipo de alta: ÓBITO)
- Describir el deterioro clínico previo al fallecimiento basándote en las evoluciones
- La ÚLTIMA línea del texto debe ser exactamente: "DESENLACE: ÓBITO - Fecha: [fecha del óbito si la hay en las evoluciones] | Hora: [hora si disponible]"
- Si no hay fecha exacta en las evoluciones, escribir: "DESENLACE: ÓBITO - Fecha: no registrada"''' if es_obito_confirmado else '''- El paciente fue dado de ALTA (NO falleció)
- Describir la condición al alta, mejoría clínica
- NUNCA mencionar fallecimiento, óbito, muerte ni términos similares
- El desenlace debe ser coherente con un alta médica'''}

REGLAS DE ESTILO:
1. Lenguaje médico técnico, estilo pase de guardia entre colegas
2. Usar verbos: evolucionó, presentó, se realizó, cursó con, se constató
3. NO mencionar fármacos específicos (van en Plan Terapéutico)
4. NO repetir "{paciente_info}" después del primer párrafo
5. NO inventar datos que no estén en las evoluciones registradas
6. Extensión mínima: 150 palabras. El texto debe ser completo y detallado.
7. NO usar separadores como "---" ni "===" en el texto
8. La frase "DESENLACE: ÓBITO" debe aparecer EXACTAMENTE UNA VEZ, como última línea del texto
9. El texto debe ser narrativo continuo en párrafos, sin encabezados ni separadores

Responde SOLO con el siguiente formato JSON:
{{
  "evolucion_medica": "..."
}}
"""

        prompt_extractor = f"""Eres un médico especialista y minero de datos clínicos (Extractor Estricto).
Tu ÚNICA función es extraer Procedimientos, Estudios e Interconsultas de la Historia Clínica.

DATOS DEL CASO:
- PACIENTE: {paciente_info if paciente_info else 'No especificado'}
- MOTIVO INTERNACIÓN: {motivo if motivo else 'No especificado'}

EVOLUCIONES MÉDICAS REGISTRADAS:
{context}

═══════════════════════════════════════════════════════════════
REGLAS DE CLASIFICACIÓN ESTRICTAS (MÁXIMA PRIORIDAD)
═══════════════════════════════════════════════════════════════

▶ "procedimientos_completos": Cirugías, punciones (punción lumbar, toracocentesis), colocación de catéteres (CVC, sonda vesical, SNG), intubación orotraqueal, drenajes, biopsias, transfusiones, diálisis, cardioversión. Formato: SOLO "Nombre del procedimiento (Fecha)". NO incluir detalles, técnicas ni descripciones.

▶ "estudios_completos": SOLO estudios por IMÁGENES y FUNCIONALES:
  - INCLUIR: Tomografía (TC/TAC), Resonancia (RMN), Radiografía (Rx), Ecografía, Ecocardiograma, Electrocardiograma (ECG), Electroencefalograma (EEG), PET, SPECT, Centellograma, Espirometría, Endoscopía (VEDA/VCC), Angiografía
  - Formato: SOLO "Nombre del estudio (Fecha)". NO incluir hallazgos, resultados ni descripciones.
  - ⛔ NO INCLUIR NUNCA: Laboratorios, hemogramas, bioquímicas, ionogramas, hepatogramas, hemocultivos, urocultivos, cultivos de LCR, serologías, PCR, gases en sangre, coagulogramas, determinaciones hormonales, vitaminas, marcadores tumorales, orina completa, glucemia, creatinina, uremia. TODO ESO VA EN LABORATORIO, NO AQUÍ.

▶ "interconsultas_completas": Especialidades médicas consultadas. Formato: "Especialidad"

- Si no encuentras items, devuelve listas vacías [].

Responde SOLO con el siguiente formato JSON:
{{
  "procedimientos_completos": ["Nombre del procedimiento (Fecha)"],
  "estudios_completos": ["Nombre del estudio (Fecha)"],
  "interconsultas_completas": ["Especialidad"]
}}
"""
        
        # 🏆 Inyectar Golden Rules a AMBOS prompts
        try:
            from app.services.golden_rules_service import get_golden_rules_for_prompt
            golden_rules = await get_golden_rules_for_prompt()
            if golden_rules:
                prompt_narrador = golden_rules + "\n\n" + prompt_narrador
                prompt_extractor = golden_rules + "\n\n" + prompt_extractor
                print(f"[EPC-JSON] Golden Rules injected into Swarm prompts: {len(golden_rules)} chars")
        except Exception as e:
            print(f"[EPC-JSON] Could not load Golden Rules: {e}")
        
        try:
            import asyncio
            result_flags_ai_procs = False
            print("[EPC-JSON] 🚀 Lanzando Swarm Multi-Agente (Narrador + Extractor) en paralelo...")
            
            tarea_narrador = ai.generate_epc(prompt_narrador)
            tarea_extractor = ai.generate_epc(prompt_extractor)
            
            result_narrador, result_extractor = await asyncio.gather(tarea_narrador, tarea_extractor)
            
            print(f"[EPC-JSON] Respuestas Swarm recibidas. Narrador: {type(result_narrador)}, Extractor: {type(result_extractor)}")
            
            evolucion = ""
            interconsultas_formatted = extract_interconsultas_chronologically(parsed.get("interconsultas", []))
            
            json_content = {}
            
            # ── NARRADOR ──
            if isinstance(result_narrador, dict):
                narr_json = result_narrador.get("json")
                if isinstance(narr_json, dict):
                    json_content.update(narr_json)
                    print(f"[EPC-JSON] Narrador JSON OK: keys={list(narr_json.keys())}")
                elif result_narrador.get("raw_text"):
                    raw_narr = result_narrador["raw_text"]
                    print(f"[EPC-JSON] Narrador: _safe_json falló, intentando parse manual del raw_text ({len(raw_narr)} chars)")
                    try:
                        clean = re.sub(r'[\x00-\x1F]+', ' ', raw_narr)
                        clean = re.sub(r'```(?:json)?\s*', '', clean)
                        clean = clean.replace('```', '').strip()
                        narr_parsed = json.loads(clean)
                        if isinstance(narr_parsed, dict):
                            json_content.update(narr_parsed)
                            print(f"[EPC-JSON] Narrador parse manual OK: keys={list(narr_parsed.keys())}")
                    except Exception as e:
                        print(f"[EPC-JSON] Narrador parse manual falló: {e}")
                    json_content["raw_text_narrador"] = raw_narr
                    
            # ── EXTRACTOR ──
            if isinstance(result_extractor, dict):
                ext_json = result_extractor.get("json")
                if isinstance(ext_json, dict):
                    json_content.update(ext_json)
                    print(f"[EPC-JSON] Extractor JSON OK: keys={list(ext_json.keys())}, estudios={len(ext_json.get('estudios_completos', []))}, procs={len(ext_json.get('procedimientos_completos', []))}")
                elif result_extractor.get("raw_text"):
                    raw_ext = result_extractor["raw_text"]
                    print(f"[EPC-JSON] Extractor: _safe_json falló, intentando parse manual del raw_text ({len(raw_ext)} chars)")
                    print(f"[EPC-JSON] Extractor raw_text preview: {raw_ext[:300]}")
                    try:
                        clean = re.sub(r'[\x00-\x1F]+', ' ', raw_ext)
                        clean = re.sub(r'```(?:json)?\s*', '', clean)
                        clean = clean.replace('```', '').strip()
                        ext_parsed = json.loads(clean)
                        if isinstance(ext_parsed, dict):
                            json_content.update(ext_parsed)
                            print(f"[EPC-JSON] Extractor parse manual OK: estudios={len(ext_parsed.get('estudios_completos', []))}, procs={len(ext_parsed.get('procedimientos_completos', []))}")
                    except Exception as e:
                        print(f"[EPC-JSON] Extractor parse manual falló: {e}, extrayendo listas con regex...")
                        # ═══ REGEX EXTRACTION DIRECTA del raw_text truncado ═══
                        clean_ext = re.sub(r'[\x00-\x1F]+', ' ', raw_ext)
                        
                        # Extraer estudios_completos
                        est_match = re.search(r'"estudios_completos"\s*:\s*\[(.*?)(?:\]|$)', clean_ext, re.DOTALL)
                        if est_match:
                            items = re.findall(r'"((?:[^"\\]|\\.)*)"', est_match.group(1))
                            items_clean = [it for it in items if len(it.strip()) > 3]
                            if items_clean:
                                json_content["estudios_completos"] = items_clean
                                print(f"[EPC-JSON] ✅ Regex extrajo {len(items_clean)} estudios del Extractor truncado")
                        
                        # Extraer procedimientos_completos
                        proc_match = re.search(r'"procedimientos_completos"\s*:\s*\[(.*?)(?:\]|$)', clean_ext, re.DOTALL)
                        if proc_match:
                            items = re.findall(r'"((?:[^"\\]|\\.)*)"', proc_match.group(1))
                            items_clean = [it for it in items if len(it.strip()) > 3]
                            if items_clean:
                                json_content["procedimientos_completos"] = items_clean
                                print(f"[EPC-JSON] ✅ Regex extrajo {len(items_clean)} procedimientos del Extractor truncado")
                        
                        # Extraer interconsultas_completas
                        ic_match = re.search(r'"interconsultas_completas"\s*:\s*\[(.*?)(?:\]|$)', clean_ext, re.DOTALL)
                        if ic_match:
                            items = re.findall(r'"((?:[^"\\]|\\.)*)"', ic_match.group(1))
                            items_clean = [it for it in items if len(it.strip()) > 2]
                            if items_clean:
                                json_content["interconsultas_completas"] = items_clean
                                print(f"[EPC-JSON] ✅ Regex extrajo {len(items_clean)} interconsultas del Extractor truncado")
                        
                    json_content["raw_text_extractor"] = raw_ext
                else:
                    print(f"[EPC-JSON] ⚠️ Extractor devolvió dict sin json ni raw_text. Keys: {list(result_extractor.keys())}")

            # Ahora extraemos la EVOLUCIÓN
            evolucion = (
                json_content.get("evolucion_epicrisis") or
                json_content.get("evolucion_medica") or
                json_content.get("evolucion") or
                str(json_content.get("raw_text_narrador", "")) or
                ""
            )

            # Limpiar markdown si hay
            if isinstance(evolucion, str) and "```" in evolucion:
                evolucion = re.sub(r"```[a-z]*\s*", "", evolucion)
                evolucion = evolucion.replace("```", "")
                
            # Extraer estudios e interconsultas completos (FASE 2 EXTRACTOR)
            if isinstance(json_content, dict):
                estudios_extra = json_content.get("estudios_completos", [])
                procs_extra = json_content.get("procedimientos_completos", [])
                ic_extra = json_content.get("interconsultas_completas", [])
                
                print(f"[EPC-JSON] Extractor retornó -> Estudios: {len(estudios_extra) if isinstance(estudios_extra, list) else 0}, Procedimientos: {len(procs_extra) if isinstance(procs_extra, list) else 0}")
                
                if isinstance(estudios_extra, list) and len(estudios_extra) > 0:
                    # Filtrar: remover vacíos Y remover laboratorios que el LLM clasificó mal
                    estudios_extra_limpios = [
                        est for est in estudios_extra 
                        if isinstance(est, str) and len(est.strip()) > 3 and not _is_lab_item(est)
                    ]
                    labs_filtrados = len(estudios_extra) - len(estudios_extra_limpios)
                    if labs_filtrados > 0:
                        print(f"[EPC-JSON] ⚠️ Filtrados {labs_filtrados} laboratorios de estudios_completos (safety net)")
                    if estudios_extra_limpios:
                        # Strip hallazgos: solo mantener "Nombre del estudio (Fecha)"
                        estudios_solo_nombre = []
                        for est in estudios_extra_limpios:
                            clean = re.split(r'\s*-\s+(?:HALLAZGOS|Hallazgos|hallazgos|Resultado|resultado|Conclusi)', est)[0]
                            clean = re.split(r'\s+-\s+', clean, maxsplit=1)[0]
                            estudios_solo_nombre.append(clean.strip())
                        
                        # REGLA DE ORO: Agrupar estudios repetidos con fechas consolidadas
                        sorted_studies = _group_studies_by_name(estudios_solo_nombre)
                        print(f"[EPC-JSON] Estudios agrupados: {len(estudios_solo_nombre)} → {len(sorted_studies)} estudios únicos")

                if isinstance(procs_extra, list) and len(procs_extra) > 0:
                    procs_extra_limpios = [proc[0].upper() + proc[1:] for proc in procs_extra if isinstance(proc, str) and len(proc.strip()) > 3]
                    if procs_extra_limpios:
                        # Strip detalles después de la fecha: solo "Nombre (Fecha)"
                        sorted_procs = []
                        for proc in procs_extra_limpios:
                            # Remove everything after "(dd/mm/yyyy)" 
                            clean = re.sub(r'(\(\d{1,2}/\d{1,2}/\d{4}\))\s*[-–—].*$', r'\1', proc).strip()
                            # Also strip " - DETALLE" if no date
                            clean = re.split(r'\s+[-–—]\s+', clean, maxsplit=1)[0].strip()
                            sorted_procs.append(clean)
                        result_flags_ai_procs = True
                        print(f"[EPC-JSON] ✅ sorted_procs SETEADO con {len(sorted_procs)} procs del LLM: {sorted_procs[:3]}")
                    else:
                        print(f"[EPC-JSON] ⚠️ procs_extra tenía {len(procs_extra)} items pero todos fueron filtrados")
                else:
                    print(f"[EPC-JSON] ⚠️ procs_extra está vacío o no es lista: type={type(procs_extra)}, len={len(procs_extra) if isinstance(procs_extra, list) else 'N/A'}")
                if isinstance(ic_extra, list):
                    for ic in ic_extra:
                        if isinstance(ic, str) and len(ic.strip()) > 2 and ic not in interconsultas_formatted:
                            interconsultas_formatted.append(ic)
            
            if not isinstance(evolucion, str):
                evolucion = str(evolucion) if evolucion else ""
            
            evolucion = evolucion.strip()
            print(f"[EPC-JSON] Evolución extraída ({len(evolucion)} chars): {evolucion[:150]}...")
            
            # Limpiar si todavía es JSON string o tiene formato JSON
            if evolucion.startswith("{") or ('"evolucion' in evolucion):
                try:
                    # Limpiar caracteres de control espurios antes de parsear
                    # (Ej: saltos de línea literales generados por la IA dentro de los strings)
                    clean_evo = re.sub(r'[\x00-\x1F]+', ' ', evolucion)
                    # Intentar parsear JSON limpio
                    parsed_json = json.loads(clean_evo)
                    if isinstance(parsed_json, dict):
                        # Re-extraer también las listas en este punto, por si _safe_json falló!
                        if not sorted_studies:
                            est_extra = parsed_json.get("estudios_completos", [])
                            if isinstance(est_extra, list):
                                sorted_studies = [e for e in est_extra if isinstance(e, str) and len(e.strip()) > 3]
                        if not sorted_procs:
                            proc_extra = parsed_json.get("procedimientos_completos", [])
                            if isinstance(proc_extra, list):
                                sorted_procs = [p[0].upper() + p[1:] for p in proc_extra if isinstance(p, str) and len(p.strip()) > 3]
                        
                        ic_extra = parsed_json.get("interconsultas_completas", [])
                        if isinstance(ic_extra, list):
                            for ic in ic_extra:
                                if isinstance(ic, str) and len(ic.strip()) > 2 and ic not in interconsultas_formatted:
                                    interconsultas_formatted.append(ic)
                        
                        evolucion = (
                            parsed_json.get("evolucion_medica") or 
                            parsed_json.get("evolucion") or
                            parsed_json.get("text") or
                            ""
                        )
                        print(f"[EPC-JSON] JSON parseado, evolución: {evolucion[:100]}...")
                except Exception as je:
                    print(f"[EPC-JSON] Error parseando JSON: {je}")
                    # ⚠️ FALLBACK: Extraer texto entre comillas si hay JSON malformado
                    # Buscar patrón "evolucion_medica": "..." o "evolucion": "..."
                    match = re.search(r'"evolucion(?:_medica)?"\s*:\s*"((?:[^"\\]|\\.)*)"', evolucion, re.DOTALL)
                    if match:
                        evolucion = match.group(1)
                        # Unescape JSON strings
                        evolucion = evolucion.replace('\\"', '"').replace('\\n', '\n')
                        print(f"[EPC-JSON] Extraído con regex: {evolucion[:100]}...")
                    else:
                        # Último recurso: quitar llaves y claves JSON
                        evolucion = re.sub(r'^[{\s]*"evolucion(?:_medica)?"\s*:\s*"?', '', evolucion)
                        evolucion = re.sub(r'"?\s*[}]*$', '', evolucion)
                        print(f"[EPC-JSON] Limpiado manualmente: {evolucion[:100]}...")
                        
                    # Extraer listas extra utilizando regex rudimentario por si se truncó el JSON del Extractor
                    raw_extractor = json_content.get("raw_text_extractor", "")
                    if raw_extractor:
                        clean_ext = re.sub(r'[\x00-\x1F]+', ' ', raw_extractor)
                        
                        if not sorted_studies:
                            estudios_match = re.search(r'"estudios_completos"\s*:\s*\[(.*?)\]?(?:\}$|,|$)', clean_ext, re.DOTALL)
                            if estudios_match:
                                items_str = estudios_match.group(1)
                                items = [m.strip(' "\'') for m in re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"?', items_str)]
                                if items:
                                    sorted_studies = [e for e in items if len(e.strip()) > 3]
                        
                        if not sorted_procs:
                            procs_match = re.search(r'"procedimientos_completos"\s*:\s*\[(.*?)\]?(?:\}$|,|$)', clean_ext, re.DOTALL)
                            if procs_match:
                                items_str = procs_match.group(1)
                                items = [m.strip(' "\'') for m in re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"?', items_str)]
                                if items:
                                    sorted_procs = [p[0].upper() + p[1:] for p in items if len(p.strip()) > 3]

            
            # Limpiar caracteres de control y normalizar espacios
            evolucion = evolucion.replace("\\n", "\n").replace('\\"', '"')
            # No eliminar todos los espacios, solo duplicados
            evolucion = re.sub(r' +', ' ', evolucion).strip()
            
            print(f"[EPC-JSON] Evolución final ({len(evolucion)} chars)")
            
        except Exception as e:
            log.error(f"[EPC-JSON] Error generando evolución: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("[EPC-JSON] No hay evoluciones, generando evolución básica")
        # Generar evolución básica sin IA si no hay evoluciones
        if motivo or parsed["diagnosticos"]:
            evolucion = f"Paciente que ingresa por {motivo}." if motivo else ""
            if parsed["diagnosticos"]:
                evolucion += f" Diagnóstico: {parsed['diagnosticos'][0]}."
    
    # 5. Construir diagnóstico principal
    diagnostico = parsed["diagnosticos"][0] if parsed["diagnosticos"] else ""
    # 6. Formatear interconsultas - AGRUPADAS POR ESPECIALIDAD
    # (Ya inicializadas al principio por extracciones LLM)
    
    print(f"[EPC-JSON] 📊 RESULTADO FINAL: procs={len(sorted_procs)}, studies={len(sorted_studies)}, ics={len(interconsultas_formatted)}")
    result = {
        "motivo_internacion": motivo,
        "diagnostico_principal_cie10": diagnostico,
        "evolucion": evolucion,
        "estudios": sorted_studies,  # NUEVA SECCIÓN: TAC, RMN, RX, etc.
        "procedimientos": sorted_procs,
        "interconsultas": interconsultas_formatted,  # Formato simplificado: Fecha - Especialidad
        "interconsultas_detalle": interconsultas_formatted,  # Igual para compatibilidad
        "laboratorios_detalle": lab_procedures,  # Lista individual de laboratorios para modal "Otros Datos de Interés"
        "medicacion": sorted_meds,
        "indicaciones_alta": [],
        "notas_alta": [],
        "_generated_by": "json_parser",
        "_ai_generated_procs": result_flags_ai_procs,
        "_meds_count": len(sorted_meds),
        "_procs_count": len(sorted_procs),
        "_studies_count": len(sorted_studies),
        "_labs_count": len(lab_procedures),
        "_ic_count": len(sorted_interconsultas),
    }
    
    if parsed["plan_seguimiento"]:
        result["notas_alta"].append(parsed["plan_seguimiento"])
    
    # =========================================================================
    # 7b. DETERMINISTIC PROCEDURE EXTRACTION from evolution text
    # In rich HCEs, structured data is mostly nursing/labs/admin entries.
    # Real clinical procedures appear in the evolution narrative text.
    # We extract them deterministically using keyword matching (no LLM).
    # =========================================================================
    tiene_evoluciones = bool(evolucion and len(evolucion) > 50)
    
    if not sorted_procs and tiene_evoluciones:
        # Keyword patterns for clinical procedures (regex, case-insensitive)
        PROCEDURE_PATTERNS = [
            # Cardiovascular
            r"(?:control|revisión|interrogación|implante|recambio)\s+(?:de(?:l)?\s+)?(?:CDI|cardiodesfibrilador|marcapasos|desfibrilador)",
            r"cardioversión\s+(?:eléctrica|farmacológica)?",
            r"cateterismo\s+(?:cardíaco|cardiaco)?",
            r"angioplastia",
            r"ablación",
            # Respiratorio
            r"intubación\s+(?:orotraqueal|endotraqueal)?",
            r"traqueostomía",
            r"ventilación\s+mecánica",
            r"toracocentesis",
            r"drenaje\s+(?:pleural|torácico)",
            r"broncoscopía",
            # Vías y catéteres
            r"(?:colocación|retiro|cambio)\s+(?:de\s+)?(?:vía\s+(?:periférica|central)|catéter\s+(?:central|venoso|arterial)|sonda\s+(?:vesical|nasogástrica|foley))",
            r"(?:retir[oó]|se\s+retir[oó])\s+(?:la\s+)?vía\s+(?:periférica|central)",
            # Quirúrgico
            r"cirugía\s+\w+",
            r"intervención\s+quirúrgica",
            r"(?:drenaje|punción|biopsia)\s+(?:de\s+)?\w+",
            # Transfusiones
            r"transfusión\s+(?:de\s+)?(?:glóbulos|sangre|plaquetas|plasma)",
            # Diálisis
            r"hemodiálisis",
            r"diálisis\s+(?:peritoneal)?",
            # Procedimientos generales
            r"paracentesis",
            r"lumbar\s+punción|punción\s+lumbar",
            r"maniobras?\s+de\s+reanimación",
            r"reanimación\s+cardiopulmonar",
            r"suspensión\s+(?:de(?:l)?\s+)?(?:soporte\s+vital|tratamiento\s+con\s+\w+)",
            r"inicio\s+(?:de\s+)?(?:tratamiento|terapia)\s+con\s+\w+",
            r"ajuste\s+(?:de\s+)?(?:tratamiento|medicación|dosis)",
        ]
        
        evol_lower = evolucion.lower()
        found_procedures = []
        seen = set()
        
        for pattern in PROCEDURE_PATTERNS:
            matches = re.finditer(pattern, evol_lower, re.IGNORECASE)
            for m in matches:
                proc_text = m.group(0).strip()
                # Capitalize first letter
                proc_text = proc_text[0].upper() + proc_text[1:]
                # Deduplicate
                key = proc_text.lower()
                if key not in seen:
                    seen.add(key)
                    found_procedures.append(proc_text)
        
        if found_procedures:
            result["procedimientos"] = found_procedures
            result["_ai_generated_procs"] = True  # Skip PostProcess date filter
            log.info(f"[EPC-JSON] Deterministic extraction: {len(found_procedures)} procedimientos from evolution text")
        else:
            log.info("[EPC-JSON] No clinical procedures found in evolution text (deterministic extraction)")
    
    # =========================================================================
    # 7c. AI FALLBACK: Solo para estudios e interconsultas vacías (raro)
    # =========================================================================
    secciones_vacias_no_procs = (
        not sorted_studies or
        not interconsultas_formatted
    )
    
    if tiene_evoluciones and secciones_vacias_no_procs:
        try:
            from app.services.ai_gemini_service import GeminiAIService as _GeminiAI
            ai_fallback = _GeminiAI()
            
            sections_to_extract = []
            if not sorted_studies:
                sections_to_extract.append('"estudios": ["Nombre del estudio"]')
            if not interconsultas_formatted:
                sections_to_extract.append('"interconsultas": ["Especialidad"]')
            
            if sections_to_extract:
                sections_json = ",\n  ".join(sections_to_extract)
                
                fallback_prompt = f"""Eres un médico especialista. Analiza la siguiente evolución y extrae SOLO lo EXPLÍCITAMENTE mencionado.

EVOLUCIÓN:
{evolucion}

INSTRUCCIONES:
1. Extrae SOLO información EXPLÍCITAMENTE mencionada
2. NO inventes datos
3. Si una sección no tiene info, déjala como []
4. NO incluir fechas, solo descripciones
5. Para "estudios": SOLO incluir estudios DIAGNÓSTICOS POR IMÁGENES o FUNCIONALES:
   - ✅ Incluir: TC, RX, Ecografía, Doppler, RMN, ECG, Ecocardiograma, EEG, PET-CT, Centellograma, Espirometría
   - ❌ NO incluir análisis de sangre/laboratorio: hemograma, glucemia, creatinina, uremia, ionograma, hepatograma, coagulograma, gasometría, PCR, VSG, eritrosedimentación, hemocultivos, urocultivos, tests rápidos, antígenos, cultivos

Responde SOLO con JSON válido:
{{
  {sections_json}
}}"""
                
                log.info("[EPC-JSON] AI fallback for empty estudios/interconsultas")
                fb_result = await ai_fallback.generate_epc(fallback_prompt)
                
                fb_data = {}
                if isinstance(fb_result, dict):
                    json_content = fb_result.get("json", fb_result)
                    if isinstance(json_content, dict):
                        fb_data = json_content
                
                if fb_data:
                    if not sorted_studies and fb_data.get("estudios"):
                        # Filter out lab/blood tests from AI-generated estudios
                        ai_estudios = [s for s in fb_data["estudios"] if isinstance(s, str) and not _is_lab_item(s)]
                        result["estudios"] = ai_estudios
                        log.info(f"[EPC-JSON] AI fallback: {len(ai_estudios)} estudios (after lab filter)")
                    if not interconsultas_formatted and fb_data.get("interconsultas"):
                        result["interconsultas"] = [ic for ic in fb_data["interconsultas"] if isinstance(ic, str)]
                        result["interconsultas_detalle"] = result["interconsultas"]
                        log.info(f"[EPC-JSON] AI fallback: {len(result['interconsultas'])} interconsultas")
        
        except Exception as e:
            log.warning(f"[EPC-JSON] AI fallback failed (non-critical): {e}")
    
    # 8. ⚠️ POST-PROCESAMIENTO CRÍTICO: Aplicar regla de óbito como respaldo
    # Si el LLM no aplicó la regla, la aplicamos aquí
    try:
        from app.services.ai_langchain_service import _post_process_epc_result, _load_section_dictionary
        procs_before_pp = len(result.get("procedimientos", []))
        dictionary_rules = await _load_section_dictionary()
        result = _post_process_epc_result(result, dictionary_rules=dictionary_rules)
        procs_after_pp = len(result.get("procedimientos", []))
        print(f"[EPC-JSON] POST-PROCESS: procs ANTES={procs_before_pp}, procs DESPUES={procs_after_pp}, dict_rules={len(dictionary_rules)}")
        if procs_before_pp > 0 and procs_after_pp == 0:
            print(f"[EPC-JSON] ⛔⛔⛔ POST-PROCESS BORRÓ TODOS LOS PROCEDIMIENTOS!")
    except Exception as e:
        print(f"[EPC-JSON] Could not apply post-processing: {e}")
    
    # =========================================================================
    # 9. ⛔ REGLA: Si taltDescripcion es OBITO, verificar contra texto
    # IMPORTANTE: El campo taltDescripcion puede estar EQUIVOCADO en Markey.
    # Si el texto de evolución indica claramente que el paciente está vivo
    # (alta médica, internación domiciliaria, se retira, etc.), NO forzar OBITO.
    # =========================================================================
    if es_obito_por_alta:
        evolucion_actual = result.get("evolucion", "")
        evolucion_lower = evolucion_actual.lower()
        
        # Indicadores claros de que el paciente está VIVO y fue dado de alta
        INDICADORES_ALTA_VIVO = [
            "se retira", "se da de alta", "alta médica", "alta sanatorial",
            "egreso a domicilio", "internación domiciliaria", "internacion domiciliaria",
            "se indica internación domiciliaria", "se indica internacion domiciliaria",
            "dado de alta", "dada de alta", "alta hospitalaria",
            "controles ambulatorios", "seguimiento ambulatorio",
            "control por consultorio", "se otorga el alta",
            "mejoría del estado general", "mejoria del estado general",
            "hemodinámicamente estable", "hemodinamicamente estable",
            "afebril", "evolución favorable", "evolucion favorable",
            "se va de alta", "egresa",
        ]
        
        paciente_vivo = any(ind in evolucion_lower for ind in INDICADORES_ALTA_VIVO)
        
        # Verificar también con el módulo de death detection
        from app.rules.death_detection import detect_death_in_text
        death_info = detect_death_in_text(evolucion_actual)
        
        if paciente_vivo and not death_info.detected:
            # ⛔ CONTRADICCIÓN: taltDescripcion dice OBITO pero el texto dice VIVO
            log.warning(f"[EPC-JSON] ⛔ CONTRADICCIÓN DETECTADA: taltDescripcion={tipo_alta} pero texto indica paciente VIVO")
            log.warning(f"[EPC-JSON] Suprimiendo DESENLACE: ÓBITO forzado - el texto médico es la fuente de verdad")
            es_obito_por_alta = False  # Suprimir
        else:
            # Óbito legítimo: proceder con el formateo
            fecha_egreso = episodio.get("inteFechaEgreso", "")
            if fecha_egreso:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(fecha_egreso.replace("Z", "+00:00"))
                    fecha_str = dt.strftime("%d/%m/%Y")
                    hora_str = dt.strftime("%H:%M")
                except:
                    fecha_str = "fecha no registrada"
                    hora_str = "hora no registrada"
            else:
                fecha_str = "fecha no registrada"
                hora_str = "hora no registrada"
            
            # Limpiar formatos de ÓBITO generados por la IA
            patrones_obito_limpiar = [
                r"PACIENTE OBIT[OÓ]\s*[-–—]\s*Fecha:\s*[^\n.]*(?:\.|$)\s*",
                r"^PACIENTE OBIT[OÓ][^\n]*\n*",
                r"PACIENTE OBIT[OÓ][^.]*\.\s*",
                r"---\s*\*?\*?DESENLACE:\s*[ÓO]BITO\*?\*?\s*Fecha[^-]*---\s*",
                r"---\s*\*?\*?DESENLACE:\s*[ÓO]BITO\*?\*?[^-]*---\s*",
                r"\n*\**DESENLACE:\s*[ÓO]BITO\**[^\n]*\n*",
                r"\n*Fecha:\s*\d{2}/\d{2}/\d{4}\s*\|\s*Hora:\s*\d{2}:\d{2}\s*$",
            ]
            for patron in patrones_obito_limpiar:
                evolucion_actual = re.sub(patron, "", evolucion_actual, flags=re.IGNORECASE | re.MULTILINE)
            
            frases_eliminar = [
                r"[^.]*(?:se retira|deambulando|por sus propios medios|dada de alta|dado de alta)[^.]*\.?\s*",
                r"[^.]*(?:alta médica|alta hospitalaria)[^.]*\.?\s*",
            ]
            for patron in frases_eliminar:
                evolucion_actual = re.sub(patron, "", evolucion_actual, flags=re.IGNORECASE)
            
            evolucion_actual = re.sub(r'---', '', evolucion_actual)
            evolucion_actual = re.sub(r'\n{3,}', '\n\n', evolucion_actual).strip()
            
            result["evolucion"] = evolucion_actual + f"\n\nDESENLACE: ÓBITO - Fecha: {fecha_str} | Hora: {hora_str}"
            result["indicaciones_alta"] = []
            result["recomendaciones"] = []
            
            log.info(f"[EPC-JSON] ⛔ FORZADO DESENLACE: ÓBITO al final desde taltDescripcion: {tipo_alta}")
    
    # =========================================================================
    # 10. ⛔ VALIDACIÓN ANTI-ALUCINACIÓN: Cruzar ÓBITO en texto vs taltDescripcion
    # Si la IA generó muerte pero el sistema dice ALTA → ELIMINAR la alucinación
    # Si la IA generó muerte y el sistema dice OBITO → REFORMATEAR al nuevo estándar
    # =========================================================================
    evolucion_final = result.get("evolucion", "")
    
    # Detectar si hay mención de muerte/óbito en el texto
    tiene_obito_texto = re.search(
        r"PACIENTE OBIT[OÓ]|DESENLACE:\s*[ÓO]BITO|constata [óo]bito|se certifica (?:la )?defunci[óo]n|falleci[óo]|fallece|falleciendo|exitus|deceso",
        evolucion_final, re.IGNORECASE
    )
    
    if tiene_obito_texto and not es_obito_por_alta:
        # ⛔ ALUCINACIÓN DETECTADA: La IA inventó un fallecimiento
        log.warning(f"[EPC-JSON] ⛔⛔⛔ ALUCINACIÓN DETECTADA: IA generó ÓBITO pero taltDescripcion={tipo_alta}")
        log.warning(f"[EPC-JSON] Eliminando falso óbito del texto")
        
        # Limpiar TODAS las menciones de muerte/óbito (exhaustivo)
        patrones_limpiar = [
            # Formato DESENLACE (generado por nuestro código o IA)
            r"\n*\**DESENLACE:\s*[ÓO]BITO\**[^\n]*\n*",
            r"---\s*\*?\*?DESENLACE:\s*[ÓO]BITO\*?\*?[^-]*---\s*",
            r"DESENLACE:\s*[ÓO]BITO[^\n]*\n*",
            # Formato PACIENTE OBITÓ
            r"PACIENTE OBIT[OÓ]\s*[-–—]\s*Fecha:[^\n.]*(?:\.|$)\s*",
            r"PACIENTE OBIT[OÓ][^.]*\.\s*",
            r"^PACIENTE OBIT[OÓ][^\n]*\n*",
            # Frases de fallecimiento
            r"[Ss]e constata [óo]bito[^.]*\.\s*",
            r"[Ss]e certifica (?:la )?defunci[óo]n[^.]*\.\s*",
            r"[Ee]l paciente fallec[eió][^.]*\.\s*",
            r"[Ll]a paciente fallec[eió][^.]*\.\s*",
            r"[Ff]allec(?:ió|e|iendo)[^.]*\.\s*",
            # Línea de Fecha/Hora suelta al final
            r"\n*Fecha:\s*(?:fecha\s+)?no\s+registrada[^\n]*\n*$",
            r"\n*Fecha:\s*\d{2}/\d{2}/\d{4}\s*\|\s*Hora:[^\n]*\n*$",
        ]
        for patron in patrones_limpiar:
            evolucion_final = re.sub(patron, "", evolucion_final, flags=re.IGNORECASE | re.MULTILINE)
        
        evolucion_final = re.sub(r'\n{3,}', '\n\n', evolucion_final).strip()
        result["evolucion"] = evolucion_final
        
        log.info(f"[EPC-JSON] ✅ Alucinación de óbito eliminada del texto")
    
    elif tiene_obito_texto and es_obito_por_alta:
        # ✅ ÓBITO LEGÍTIMO: reformatear si tiene formato viejo
        tiene_formato_nuevo = "DESENLACE: ÓBITO" in evolucion_final.upper()
        tiene_formato_viejo = re.search(r"PACIENTE OBIT[OÓ]", evolucion_final, re.IGNORECASE)
        
        if tiene_formato_viejo and not tiene_formato_nuevo:
            # Extraer fecha y hora del formato viejo
            match_fecha = re.search(r"Fecha:\s*(\d{1,2}/\d{1,2}/\d{4})", evolucion_final)
            match_hora = re.search(r"Hora:\s*(\d{1,2}:\d{2}|hora no registrada)", evolucion_final, re.IGNORECASE)
            
            fecha_str = match_fecha.group(1) if match_fecha else "fecha no registrada"
            hora_str = match_hora.group(1) if match_hora else "hora no registrada"
            
            # Limpiar formato viejo
            patrones_obito_viejo = [
                r"PACIENTE OBIT[OÓ]\s*[-–—]\s*Fecha:\s*[^\n.]*(?:\.|$)\s*",
                r"^PACIENTE OBIT[OÓ][^\n]*\n*",
                r"PACIENTE OBIT[OÓ][^.]*\.\s*",
            ]
            for patron in patrones_obito_viejo:
                evolucion_final = re.sub(patron, "", evolucion_final, flags=re.IGNORECASE)
            
            evolucion_final = re.sub(r'\n{3,}', '\n\n', evolucion_final).strip()
            
            bloque_obito = f"""

---
**DESENLACE: ÓBITO**
Fecha: {fecha_str} | Hora: {hora_str}
---"""
            result["evolucion"] = evolucion_final + bloque_obito
            result["indicaciones_alta"] = []
            result["recomendaciones"] = []
            
            log.info(f"[EPC-JSON] ⛔ REFORMATEADO ÓBITO legítimo: {fecha_str} {hora_str}")
    
    log.info(f"[EPC-JSON] EPC generada: meds={len(sorted_meds)}, procs={len(sorted_procs)}, ics={len(interconsultas_formatted)}")
    
    # ------------------------------------------------------------------
    # FALLBACK: Si motivo está vacío, inferir con LLM desde evolución
    # ------------------------------------------------------------------
    _m = (result.get("motivo_internacion") or "").strip()
    print(f"[EPC-JSON] MOTIVO-FALLBACK check: motivo='{_m}' evolucion_len={len(result.get('evolucion', ''))}")
    if not _m or _m.lower() in ("no especificado en hce", "no especificado"):
        _evo = (result.get("evolucion") or "")[:4000]
        if _evo and len(_evo) > 50:
            try:
                print("[EPC-JSON] MOTIVO-FALLBACK: Inferiendo motivo con LLM...")
                _fb_ai = GeminiAIService()
                _fb_prompt = (
                    "Eres un médico clínico experto. A partir del siguiente texto de evolución clínica, "
                    "determina cuál fue el MOTIVO DE INTERNACIÓN del paciente. "
                    "Responde ÚNICAMENTE el motivo, en lenguaje médico profesional, "
                    "máximo 30 palabras. NO incluyas la edad, sexo ni fecha de ingreso. "
                    "Sé conciso y preciso. Responde SOLO el texto del motivo, sin comillas ni explicaciones.\n\n"
                    f"Evolución clínica:\n{_evo}"
                )
                _fb_result = await _fb_ai.generate_epc(_fb_prompt, want_json=False)
                _fb_text = (_fb_result.get("raw_text", "") if isinstance(_fb_result, dict) else str(_fb_result)).strip().strip('"').strip("'").strip()
                _fb_words = _fb_text.split()
                if len(_fb_words) > 30:
                    _fb_text = " ".join(_fb_words[:30])
                if _fb_text and len(_fb_text) > 5:
                    result["motivo_internacion"] = f"No especificado en HCE ({_fb_text})"
                    print(f"[EPC-JSON] MOTIVO-FALLBACK OK: {result['motivo_internacion'][:100]}")
            except Exception as e:
                print(f"[EPC-JSON] MOTIVO-FALLBACK ERROR: {e}")
    
    return result

