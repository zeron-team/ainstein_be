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
        return datetime.strptime(ic.get('fecha', ''), "%d/%m/%Y %H:%M")
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
        
        # Parsear fecha
        fecha_str = ""
        if fecha:
            try:
                dt = datetime.fromisoformat(fecha.replace("Z", "+00:00"))
                fecha_str = dt.strftime("%d/%m/%Y %H:%M")
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
            
            # NOTA: No agregar interconsultas desde procedimientos
            # Las interconsultas solo vienen del tipo de registro "EVOLUCION DE INTERCONSULTA"
            
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
        
        # 4. Extraer EVOLUCIONES
        evolucion = entry.get("entrEvolucion", "")
        if evolucion:
            # Limpiar entidades HTML
            evolucion = clean_html_text(evolucion)
        if evolucion and len(evolucion) > 50:
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
        
        # 6. Procesar PLANTILLAS (Epicrisis, Anamnesis, etc.)
        plantillas = entry.get("plantillas", []) or []
        for plantilla in plantillas:
            grupo = plantilla.get("grupDescripcion", "")
            propiedades = plantilla.get("propiedades", []) or []
            
            if grupo == "ANAMNESIS":
                for prop in propiedades:
                    nombre = prop.get("grprDescripcion", "")
                    valor = prop.get("engpValor", "") or ""
                    
                    # Limpiar HTML entities PRIMERO
                    valor = clean_html_text(valor) if valor else ""
                    
                    if "Motivo de Internación" in nombre:
                        # Limpiar tags HTML
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
            
            elif grupo == "EPICRISIS":
                for prop in propiedades:
                    nombre = prop.get("grprDescripcion", "")
                    valor = prop.get("engpValor", "") or ""
                    
                    # Limpiar HTML entities
                    valor = clean_html_text(valor) if valor else ""
                    
                    if "Motivo de Internación" in nombre and not result["motivo_internacion"]:
                        motivo = re.sub(r"<[^>]+>", "", valor).strip()
                        result["motivo_internacion"] = motivo
                    
                    if "Tratamiento al alta" in nombre:
                        result["tratamiento_alta"] = re.sub(r"<[^>]+>", "", valor).strip()
                    if "Plan de seguimiento" in nombre:
                        result["plan_seguimiento"] = re.sub(r"<[^>]+>", "", valor).strip()
    
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

def sort_and_group_procedures(procedures: List[Dict[str, Any]]) -> List[str]:
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
        
        # Rutinas de enfermería
        "SONDA NASOGASTRICA", "ASPIRACION SECRECIONES",
        
        # Controles genéricos
        "CONTROL DE", "SIGNOS VITALES", "SATURACION", "TEMPERATURA",
        "FRECUENCIA CARDIACA", "FRECUENCIA RESPIRATORIA",
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
    hidden_categories = {
        "control", "higiene", "enfermeria", 
        "valoracion", "medicacion_admin", "valoracion_clinica",
        "interconsulta",  # Ya están en su sección
    }
    
    def parse_date(p):
        fecha = p.get("fecha", "")
        try:
            return datetime.strptime(fecha, "%d/%m/%Y %H:%M")
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
    akm_count = 0
    
    # Procedimientos importantes individuales
    important_procs = []
    
    for p in procedures:
        categoria = p.get("categoria", "otro")
        descripcion = p.get("descripcion", "")
        desc_upper = descripcion.upper()
        
        # 1. Verificar si es laboratorio - AGRUPAR, no mostrar individualmente
        if categoria == "laboratorio" or is_lab_procedure(descripcion):
            lab_count += 1
            continue  # No agregar individualmente, se agrupa al final
        
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
        
        # 5. Más keywords a ocultar (rutina que no entra en categorías)
        skip_keywords = [
            "OBSERVACION", "SUEÑO", "REPOSO", "PASE DE", 
            "REGISTROS", "CONFECCION", "ARREGLO", "ORDEN DE",
            "INFORMACION AL", "ENTREVISTA", "AVISO",
            "RETIRAR VIA", "PERMEABILIDAD", "ACCESO VENOSO",
            "VALORACION DLEE", "VALORACION DE", "VALORACION DEL",
            "PULSERA", "TRASLADO", "CABECERA", "BARANDAS",
            "DECUBITO", "ALMOHADA", "CHATA", "ORINAL",
        ]
        
        should_skip = any(kw in desc_upper for kw in skip_keywords)
        if should_skip:
            continue
        
        # ¡Este procedimiento es importante! Agregarlo
        important_procs.append(p)
    
    # Ordenar cronológicamente
    important_procs.sort(key=parse_date)
    
    result = []
    seen = set()  # Evitar duplicados
    
    # Agregar resumen de laboratorios al INICIO si hubo
    if lab_count > 0:
        result.append(f"Laboratorios realizados ({lab_count} estudios)")
    
    # Procesar procedimientos importantes (sin emojis)
    for p in important_procs:
        fecha = p.get("fecha", "")
        descripcion = p.get("descripcion", "")
        
        # Clave única para evitar duplicados (solo por descripción, no fecha)
        desc_key = descripcion.upper().strip()
        if desc_key in seen:
            continue
        seen.add(desc_key)
        
        # Formato limpio
        if fecha and descripcion:
            result.append(f"{fecha} - {descripcion}")
        elif descripcion:
            result.append(descripcion)
    
    # Agregar AKM agrupado al final si hubo
    if akm_count > 0:
        result.append(f"Asistencia kinésica motora durante la internación ({akm_count} sesiones)")
    
    return result


def sort_procedures_chronologically(procedures: List[Dict[str, Any]]) -> List[str]:
    """Alias para compatibilidad - usa la nueva función de agrupación."""
    return sort_and_group_procedures(procedures)


async def generate_epc_from_json(
    hce_doc: Dict[str, Any],
    patient_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Genera EPC desde documento HCE JSON estructurado.
    
    Args:
        hce_doc: Documento HCE de MongoDB (con estructura ainstein)
        patient_id: ID del paciente (opcional)
        
    Returns:
        Dict con estructura EPC completa
    """
    from app.services.ai_gemini_service import GeminiAIService
    
    log.info("[EPC-JSON] Generando EPC desde JSON estructurado")
    
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
    
    # 2. Ordenar medicación alfabéticamente
    sorted_meds = sort_medications_alphabetically(parsed["medicacion"])
    
    # 3. Ordenar procedimientos cronológicamente
    sorted_procs = sort_procedures_chronologically(parsed["procedimientos"])
    
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
        prompt = f"""
Genera un texto de EVOLUCIÓN médica para una epicrisis basado en estos datos:

PACIENTE: {paciente_info if paciente_info else 'No especificado'}
MOTIVO INTERNACIÓN: {motivo if motivo else 'No especificado'}
DIAGNÓSTICOS: {todos_diagnosticos}
PROCEDIMIENTOS REALIZADOS: {todos_procedimientos}
PARTE QUIRÚRGICO: {parsed['parte_quirurgico'] if parsed['parte_quirurgico'] else 'N/A'}

EVOLUCIONES MÉDICAS REGISTRADAS (TEXTO COMPLETO):
{context}

═══════════════════════════════════════════════════════════════
⛔⛔⛔ REGLA CRÍTICA DE FALLECIMIENTO - NO NEGOCIABLE ⛔⛔⛔
═══════════════════════════════════════════════════════════════

Esta es la regla MÁS IMPORTANTE. DEBES verificarla ANTES de generar la respuesta.

SI en CUALQUIER evolución aparece:
- "fallece", "falleció", "fallecio", "falleciendo"
- "óbito", "obito", "obitó", "éxitus", "exitus"
- "murió", "murio", "defunción"
- "constata", "se constata" (común: "se constata óbito")
- "paro cardiorrespiratorio"
- "maniobras de reanimación", "RCP"
- "sin respuesta a maniobras"
- CUALQUIER indicación explícita o implícita de muerte

ENTONCES el ÚLTIMO PÁRRAFO OBLIGATORIAMENTE DEBE comenzar con:

"PACIENTE OBITÓ - Fecha: {{fecha}} Hora: {{hora}}. {{descripción}}"

⚠️ IMPORTANTE: Busca la FECHA y HORA del fallecimiento en el texto. Si no está explícita, usa "hora no registrada".

EJEMPLOS CORRECTOS:
✓ "PACIENTE OBITÓ - Fecha: 29/07/2025 Hora: 22:00. Se acude a llamado de enfermería manifestando paro cardiorrespiratorio. Se intentan maniobras de reanimación sin respuesta. Se constata óbito."
✓ "PACIENTE OBITÓ - Fecha: 15/03/2025 Hora: 14:30. Evolucionó con shock séptico refractario a vasopresores."

EJEMPLOS INCORRECTOS (NUNCA HACER):
❌ "Evoluciona desfavorablemente y fallece."
❌ "Paciente presenta óbito el día 15/03."
❌ "Finalmente el paciente muere."

═══════════════════════════════════════════════════════════════

REGLAS GENERALES OBLIGATORIAS:
1. OBLIGATORIO: Comenzar con "{paciente_info}, " seguido de antecedentes relevantes si los hay
2. Texto médico técnico, estilo pase entre colegas (no narrativo coloquial)
3. Estructura: 2-4 párrafos coherentes
   - Párrafo 1: Antecedentes + motivo de ingreso
   - Párrafo 2-3: Evolución durante internación, procedimientos, complicaciones
   - Párrafo final: Desenlace (alta o óbito)
4. NO mencionar fármacos específicos (van en Plan Terapéutico)
5. NO repetir "{paciente_info}" después del primer párrafo
6. NO inventar datos que no estén en las evoluciones
7. Usar lenguaje médico preciso: evolucionó, presentó, se realizó, cursó con

Responde SOLO con el texto de evolución en formato JSON:
{{"evolucion_medica": "..."}}
"""
        
        try:
            result = await ai.generate_epc(prompt)
            print(f"[EPC-JSON] Respuesta IA tipo: {type(result)}, keys: {result.keys() if isinstance(result, dict) else 'N/A'}")
            
            evolucion = ""
            
            if isinstance(result, dict):
                # Estructura real: {'json': {'evolucion_epicrisis': '...'}, '_provider': '...'}
                json_content = result.get("json", {})
                if isinstance(json_content, dict):
                    evolucion = (
                        json_content.get("evolucion_epicrisis") or
                        json_content.get("evolucion_medica") or
                        json_content.get("evolucion") or
                        json_content.get("text") or
                        ""
                    )
                
                # Si no encontramos en json, buscar en el nivel superior
                if not evolucion:
                    evolucion = (
                        result.get("raw_text") or 
                        result.get("evolucion") or
                        result.get("evolucion_medica") or
                        result.get("evolucion_epicrisis") or
                        result.get("text") or
                        ""
                    )
                
                # Limpiar markdown si hay
                if isinstance(evolucion, str) and "```" in evolucion:
                    evolucion = re.sub(r"```[a-z]*\s*", "", evolucion)
                    evolucion = evolucion.replace("```", "")
                    
            elif isinstance(result, str):
                evolucion = result
            
            if not isinstance(evolucion, str):
                evolucion = str(evolucion) if evolucion else ""
            
            evolucion = evolucion.strip()
            print(f"[EPC-JSON] Evolución extraída ({len(evolucion)} chars): {evolucion[:150]}...")
            
            # Limpiar si todavía es JSON string
            if evolucion.startswith("{") and ("evolucion" in evolucion or "evolucion_medica" in evolucion):
                try:
                    import json
                    parsed_json = json.loads(evolucion)
                    if isinstance(parsed_json, dict):
                        evolucion = (
                            parsed_json.get("evolucion_medica") or 
                            parsed_json.get("evolucion") or
                            parsed_json.get("text") or
                            ""
                        )
                        print(f"[EPC-JSON] JSON parseado, evolución: {evolucion[:100]}...")
                except Exception as je:
                    print(f"[EPC-JSON] Error parseando JSON: {je}")
            
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
    
    # 6. Formatear interconsultas - Agrupar por especialidad con resumen
    # Objetivo: mostrar max 3 interconsultas agrupadas por especialidad
    from collections import defaultdict
    
    ic_by_specialty = defaultdict(list)
    for ic in parsed["interconsultas"]:
        especialidad = ic.get('especialidad', '')
        if especialidad:
            ic_by_specialty[especialidad].append(ic)
    
    interconsultas_formatted = []
    
    for especialidad, ics in ic_by_specialty.items():
        if not ics:
            continue
        
        # Ordenar por fecha
        ics_sorted = sorted(ics, key=_parse_interconsulta_date)
        
        # Extraer rango de fechas
        primera_fecha = ics_sorted[0].get('fecha', '')[:10] if ics_sorted else ''
        ultima_fecha = ics_sorted[-1].get('fecha', '')[:10] if len(ics_sorted) > 1 else ''
        
        # Determinar resumen según cantidad
        if len(ics_sorted) == 1:
            # Una sola interconsulta - mostrar completa
            obs = ics_sorted[0].get('observacion', '')
            resumen = ""
            if obs:
                # Limpiar y resumir
                if "Paciente cursa" in obs:
                    resumen = obs.split("Paciente cursa")[-1][:60].strip()
                elif "Paciente de" in obs and "." in obs:
                    parts = obs.split(".")
                    for part in parts[1:]:
                        if len(part.strip()) > 10:
                            resumen = part.strip()[:60]
                            break
                else:
                    resumen = obs[:60]
            
            ic_str = f"{primera_fecha} - {especialidad}"
            if resumen:
                ic_str += f": {resumen}"
            interconsultas_formatted.append(ic_str)
        else:
            # Múltiples interconsultas - mostrar cada una con su fecha y resumen corto
            # Encabezado con la especialidad
            if primera_fecha == ultima_fecha:
                header = f"{primera_fecha}: {especialidad}"
            else:
                header = f"{primera_fecha} - {ultima_fecha}: {especialidad} ({len(ics_sorted)} seguimientos)"
            interconsultas_formatted.append(header)
            
            # Listar cada seguimiento con fecha y mini-resumen
            for ic in ics_sorted:
                fecha = ic.get('fecha', '')[:10]  # Solo la fecha sin hora
                obs = ic.get('observacion', '')
                
                # Extraer resumen útil y completo
                mini_resumen = ""
                if obs:
                    # Normalizar espacios
                    obs_clean = re.sub(r'\s+', ' ', obs)
                    
                    # Estrategia 1: Buscar palabras clave de seguimiento post-operatorio
                    if re.search(r'\d+[°ª]?\s*d[ií]a\s*(?:de\s*)?POP', obs_clean, re.I):
                        mini_resumen = "Seguimiento post-operatorio"
                    
                    # Estrategia 2: Buscar diagnóstico o impresión
                    elif re.search(r'\b(?:idx|dx|diagnóstico|impresión):', obs_clean, re.I):
                        match = re.search(r'\b(?:idx|dx|diagnóstico|impresión):\s*([^.]+)', obs_clean, re.I)
                        if match:
                            mini_resumen = match.group(1).strip()[:100]
                    
                    # Estrategia 3: Buscar lo que se solicita
                    elif re.search(r'\b(?:solicito|solicita|se solicita)', obs_clean, re.I):
                        match = re.search(r'\b(?:solicito|solicita|se solicita)\s+([^.]+)', obs_clean, re.I)
                        if match:
                            mini_resumen = "Solicita: " + match.group(1).strip()[:80]
                    
                    # Estrategia 4: Buscar estado actual del paciente
                    elif re.search(r'\bactualmente\b', obs_clean, re.I):
                        match = re.search(r'\bactualmente\s+([^.]+\.)', obs_clean, re.I)
                        if match:
                            frase = match.group(1).strip()
                            # Tomar hasta el primer punto o 100 chars
                            mini_resumen = frase[:100] if len(frase) <= 100 else frase[:100].rsplit(' ', 1)[0] + "..."
                    
                    # Estrategia 5: Tomar primera frase significativa (saltar antecedentes)
                    if not mini_resumen:
                        # Buscar frases que NO sean antecedentes
                        frases = obs_clean.split('.')
                        for i, frase in enumerate(frases):
                            frase = frase.strip()
                            # Saltar frases muy cortas o que hablan de antecedentes
                            if len(frase) < 20:
                                continue
                            if i == 0 and re.search(r'\bantecedente', frase, re.I):
                                continue
                            # Tomar esta frase
                            mini_resumen = frase[:100] if len(frase) <= 100 else frase[:100].rsplit(' ', 1)[0] + "..."
                            break
                    
                    # Último recurso: tomar del inicio cortando en palabra
                    if not mini_resumen and len(obs_clean) > 20:
                        if len(obs_clean) <= 100:
                            mini_resumen = obs_clean
                        else:
                            mini_resumen = obs_clean[:100].rsplit(' ', 1)[0] + "..."
                
                # Formatear línea
                if mini_resumen:
                    sub_ic = f"  - {fecha}: {mini_resumen}"
                else:
                    sub_ic = f"  - {fecha}"
                interconsultas_formatted.append(sub_ic)
    
    # 7. Construir resultado final
    result = {
        "motivo_internacion": motivo,
        "diagnostico_principal_cie10": diagnostico,
        "evolucion": evolucion,
        "procedimientos": sorted_procs,
        "interconsultas": interconsultas_formatted,
        "medicacion": sorted_meds,
        "indicaciones_alta": [],
        "notas_alta": [],
        "_generated_by": "json_parser",
        "_meds_count": len(sorted_meds),
        "_procs_count": len(sorted_procs),
        "_ic_count": len(interconsultas_formatted),
    }
    
    if parsed["plan_seguimiento"]:
        result["notas_alta"].append(parsed["plan_seguimiento"])
    
    # 8. ⚠️ POST-PROCESAMIENTO CRÍTICO: Aplicar regla de óbito como respaldo
    # Si el LLM no aplicó la regla, la aplicamos aquí
    try:
        from app.services.ai_langchain_service import _post_process_epc_result
        result = _post_process_epc_result(result)
        log.info("[EPC-JSON] Applied death rule post-processing")
    except Exception as e:
        log.warning(f"[EPC-JSON] Could not apply post-processing: {e}")
    
    # =========================================================================
    # 9. ⛔ REGLA OBLIGATORIA: Si taltDescripcion es OBITO, FORZAR formato
    # Aunque las evoluciones no lo mencionen, el alta indica fallecimiento
    # =========================================================================
    if es_obito_por_alta:
        evolucion_actual = result.get("evolucion", "")
        
        # Si NO tiene "PACIENTE OBITÓ", agregarlo
        if "PACIENTE OBITÓ" not in evolucion_actual.upper():
            # Buscar fecha de egreso
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
            
            # Eliminar frases contradictorias de alta
            frases_eliminar = [
                r"[^.]*(?:se retira|deambulando|por sus propios medios|dada de alta|dado de alta)[^.]*\.?\s*",
                r"[^.]*(?:alta médica|alta hospitalaria)[^.]*\.?\s*",
            ]
            for patron in frases_eliminar:
                evolucion_actual = re.sub(patron, "", evolucion_actual, flags=re.IGNORECASE)
            
            # Agregar línea de óbito al final
            linea_obito = f"\n\nPACIENTE OBITÓ - Fecha: {fecha_str} Hora: {hora_str}. Tipo de alta registrado: {tipo_alta}."
            result["evolucion"] = evolucion_actual.strip() + linea_obito
            
            # Limpiar indicaciones y recomendaciones
            result["indicaciones_alta"] = []
            result["recomendaciones"] = []
            
            log.info(f"[EPC-JSON] ⛔ FORZADO PACIENTE OBITÓ desde taltDescripcion: {tipo_alta}")
    
    log.info(f"[EPC-JSON] EPC generada: meds={len(sorted_meds)}, procs={len(sorted_procs)}, ics={len(interconsultas_formatted)}")
    
    return result

