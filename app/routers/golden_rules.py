"""
Golden Rules API — Manages EPC generation rules.
Sections are stored in MongoDB collection 'golden_rules'.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.deps import get_current_user, get_db
from app.adapters.mongo_client import get_mongo_db

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/golden-rules", tags=["golden-rules"])

# ──────────────────────────────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────────────────────────────

class RuleItem(BaseModel):
    id: Optional[str] = None
    text: str
    priority: str = "normal"  # critica | alta | normal
    active: bool = True


class RuleSection(BaseModel):
    key: str
    title: str
    rules: List[RuleItem]


class RuleSectionUpdate(BaseModel):
    rules: List[RuleItem]


# ──────────────────────────────────────────────────────────────────────
# Default sections and seed rules (from REGLAS_GENERACION_EPC.md)
# ──────────────────────────────────────────────────────────────────────

DEFAULT_SECTIONS = [
    {
        "key": "core",
        "title": "Reglas Core",
        "rules": [
            {"text": "1. LECTURA 100% ESTRICTA: Analiza obligatoriamente todo el contexto provisto sin realizar sesgos iniciales ni resúmenes prematuros. Prohibido truncar o ignorar datos de fechas antiguas; considera toda la historia clínica como evidencia activa.", "priority": "critica", "active": True},
            {"text": "2. TOLERANCIA CERO A ALUCINACIONES (CERO INVENCIÓN): Solo puedes usar datos presentes textualmente en la HCE. Prohibido deducir diagnósticos, inventar fechas no documentadas o suponer resoluciones de síntomas. Si una sección carece de datos, déjala estrictamente vacía.", "priority": "critica", "active": True},
            {"text": "3. FIDELIDAD ESTILÍSTICA ('PASE ENTRE COLEGAS'): Redacta utilizando jerga médico-técnica, densa y formal. Formula el texto como si fuese un sumario de un especialista para derivar a otro especialista. Nunca uses lenguaje coloquial o dirigido al paciente.", "priority": "alta", "active": True},
            {"text": "4. FILTRADO CLÍNICO DE RUIDO (LOOK VS DO): Ignora y excluye sistemáticamente rutinas de enfermería (controles vitales, valoraciones, higiene) y fluidos de mantenimiento (dextrosa basal, solución fisiológica, plan de hidratación) a menos que su inicio o suspensión representen la resolución de un shock o hito crítico.", "priority": "alta", "active": True},
            {"text": "5. CRONOLOGÍA SECUENCIAL ESTRICTA: Relata los eventos en orden cronológico ascendente. Estructura general: 1) Antecedentes base relevantes, 2) Motivo fáctico de la internación actual, 3) Evolución médica y conductual por días o periodos, 4) Condición final. Jamás adelantes desenlaces de días futuros al inicio del texto clínico.", "priority": "alta", "active": True},
            {"text": "6. DESPERSONALIZACIÓN IMPERSONAL: Escribe estrictamente en formato pasivo y abstracto de tercera persona. Prohibido el uso de la primera persona singular o plural (nunca uses 'indiqué', 'observamos', 'decidimos'). Usa fórmulas universales como 'se constata', 'paciente evoluciona', 'se indica'.", "priority": "normal", "active": True},
            {"text": "7. AGRUPACIÓN LÓGICA CONTINUA (ANTI-DUPLICACIÓN): Detecta patrones de continuidad terapéutica. Si una conducta clínica o esquema (ej. infusión antibiótica o aislamiento) persiste sin cambios por varios días, comprímelos en un solo enunciado conclusivo (Ej: 'Cumplió esquema de Ceftriaxona por 7 días con buena tolerancia'). No documentes reiterativamente la misma conducta diaria.", "priority": "alta", "active": True},
            {"text": "8. SALVAGUARDA FORENSE (ÓBITO Y SHOCK): Ante el evento de un fallecimiento o paro cardiorrespiratorio, cambia inmediatamente el registro a un formato pericial-descriptivo de máxima precisión. Detalla obligatoriamente: hora exacta, signos clínicos de compromiso severo, terapias completas de reanimación aplicadas, respuesta y, si se declaran, las causas de muerte directas e intervinientes secuenciales.", "priority": "critica", "active": True},
            {"text": "9. BLINDAJE ANTI-EPICRISIS PREVIAS (FUENTE PURA): Queda estrictamente prohibido utilizar, extraer información o copiar contenido de cualquier sección etiquetada o titulada como 'Epicrisis' dentro de la Historia Clínica y plantillas documentales. La información debe sintetizarse desde las evoluciones nativas, partes diarios y registros operativos puros, asegurando que no se recicle un resumen anterior.", "priority": "critica", "active": True},
            {"text": "10. INTEGRIDAD DE EXTRACCIÓN (ANTI-TRUNCAMIENTO): Al extraer o listar textos médicos (procedimientos, diagnósticos, etc.), NUNCA trunques los nombres. Extrae la frase anatómica o técnica completa. Está terminantemente prohibido generar frases terminadas en preposiciones cortadas (ej. descarta un 'Cirugía en' o 'Tratamiento de'). Si un texto en el documento original está ilegiblemente cortado de ese modo, omítelo completamente.", "priority": "alta", "active": True},
        ],
    },
    {
        "key": "motivo",
        "title": "Motivo de internación",
        "rules": [
            {"text": "1. FUENTE TEMPORAL ESTRICTA (DÍA 1): Extrae el motivo DIRECTAMENTE de la Anamnesis, primera nota de admisión o consulta inicial. Está terminantemente prohibido extraer información de resúmenes de egreso (Epicrisis), evoluciones de días posteriores o complicaciones intra-hospitalarias (ej. neumonía intrahospitalaria).", "priority": "critica", "active": True},
            {"text": "2. FOCO CLÍNICO DE ADMISIÓN: Redacta exclusivamente el síntoma, signo, o síndrome agudo que disparó la necesidad de internación. Inhibición absoluta: NO incluyas diagnósticos prospectivos confirmados más tarde ni antecedentes patológicos previos, a menos que sean la causa directa de internación.", "priority": "critica", "active": True},
            {"text": "3. PROTOCOLOS DE INGRESO ESPECIAL: Trauma/Accidentes: Describe Causa + Lesión inicial (Ej: Caída con fractura de fémur). Cirugía Programada: Procedimiento + Patología base. Derivación: Motivo de traslado + Institución origen (si consta).", "priority": "alta", "active": True},
            {"text": "4. FORMATO DE ALTA PRECISIÓN: Redacción telegráfica ultra-concisa de 15 a 30 palabras máximo. Prohibido usar mayúsculas sostenidas, nombres de pacientes, fechas o detallar la fisiopatología.", "priority": "alta", "active": True},
            {"text": "5. FALLBACK DE INFERENCIA DE IA: Si la historia carece por completo de nota de ingreso visible, deduce el motivo sintomático leyendo las primeras intervenciones médicas y enciérralo entre paréntesis para indicar que fue inferido de forma secundaria.", "priority": "normal", "active": True},
        ],
    },
    {
        "key": "evolucion",
        "title": "Evolución",
        "rules": [
            {"text": "1. PUREZA DE FUENTES: Construye el texto EXCLUSIVAMENTE a partir de documentos nativos médicos (EVOLUCION MEDICA, PARTE QUIRURGICO, INGRESO DE PACIENTE). Queda estrictamente vedado el uso de Hojas de Enfermería, Balances o Indicaciones como base narrativa.", "priority": "critica", "active": True},
            {"text": "2. ARQUITECTURA TEMPORAL Y SISTÉMICA: Relata los eventos en estricto tiempo pasado y orden cronológico. Estructura el cuerpo principal desglosando la evolución por sistemas y/o especialidades (Cardiológico, Respiratorio, Infectológico, Neurológico) agrupando fechas clave.", "priority": "alta", "active": True},
            {"text": "3. PROTOCOLO INFECTOLÓGICO Y DE CULTIVOS: Al documentar cuadros infecciosos, es obligatorio detallar: Germen aislado, esquema antibiótico específico (fármaco, dosis, vía, y duración exacta en días), si las muestras fueron tomadas pre o intra-antibiótico, y la respuesta clínica al tratamiento.", "priority": "alta", "active": True},
            {"text": "4. HITOS DE RIESGO Y TERAPIA INTENSIVA: Las estadías en unidades cerradas (UTI/UCO) deben tener fecha de ingreso/egreso. Identifica explícitamente los días de Asistencia Respiratoria Mecánica (ARM) y soporte vasopresor/inotrópico. Documenta cualquier Limitación del Esfuerzo Terapéutico (LET) discutida con la familia.", "priority": "alta", "active": True},
            {"text": "5. PRECISIÓN EN PROCEDIMIENTOS E INTERCONSULTAS: Ante intervenciones quirúrgicas o estudios invasivos, menciona fecha, nombre técnico del procedimiento y hallazgo principal. Resume las interconsultas detallando únicamente la recomendación crítica o conducta instaurada por el especialista.", "priority": "normal", "active": True},
            {"text": "6. DESENLACE LEGAL EN ÓBITOS: Ante un fallecimiento u óbito en sala, aplica la normativa argentina: describe las maniobras de RCP precisas y documenta explícitamente la causa de muerte encadenada (causa básica, interviniente y directa).", "priority": "critica", "active": True},
            {"text": "7. ESTADO AL EGRESO (ALTA/DERIVACIÓN): Si el paciente egresa vivo, el párrafo final debe ser una fotografía clínica: detalla el examen físico de salida de relevancia, el destino de egreso (domicilio, rehabilitación, derivación) y el plan estricto de seguimiento ambulatorio (estudios o controles que el médico solicitó a futuro).", "priority": "alta", "active": True},
        ],
    },
    {
        "key": "procedimientos",
        "title": "Procedimientos",
        "rules": [
            {"text": "0. DEFINICIÓN CORE: Sos un médico clínico. Definí 'Procedimientos' como toda intervención terapéutica, quirúrgica o diagnóstica invasiva/no invasiva. Incluyen cirugías (programadas/urgencia, técnica), endoscopías, cateterismos, punciones, y procedimientos menores (drenajes, suturas complejas, reducciones, dispositivos). Captura: tipo de procedimiento y fecha. Solo incluye los que modificaron el curso clínico o plan terapéutico.", "priority": "critica", "active": True},
            {"text": "1. FILTRO INVASIVO DIRECTO: Incluye exclusivamente procedimientos quirúrgicos, biopsias, catéteres, sondas e intubaciones. Excluye imágenes médicas (van a Estudios) y rutinas de enfermería. PROHÍBE RIGUROSAMENTE las Interconsultas o menciones a Especialidades Médicas (ej: Otorrinolaringología, Neurología, etc), las cuales deben ser purgadas de aquí e ir a su sección nativa.", "priority": "critica", "active": True},
            {"text": "2. ARQUITECTURA CRONOLÓGICA: Ordena los procedimientos con fecha entre paréntesis. Si hay procedimientos compuestos de un mismo tiempo quirúrgico, agrúpalos como un evento único.", "priority": "alta", "active": True},
            {"text": "3. TOPOGRAFÍA Y TÉCNICA: Específica la localización anatómica exacta (sitio de inserción, lecho vascular). En cirugías, anota brevemente el hallazgo intraoperatorio.", "priority": "alta", "active": True},
            {"text": "4. DURACIÓN DE SOPORTES: Para Asistencia Respiratoria Mecánica (ARM) e Infusiones/Nutrición enteral es obligatorio detallar las fechas de inicio a fin.", "priority": "alta", "active": True},
            {"text": "5. FILTRO DE LABORATORIO: Los exámenes de sangre de rutina están excluidos, salvo hallazgo drástico ausente en evolución.", "priority": "normal", "active": True},
        ],
    },
    {
        "key": "estudios",
        "title": "Estudios",
        "rules": [
            {"text": "0. DEFINICIÓN CORE: Sos un médico clínico. Definí 'Estudios' como el registro de estudios diagnósticos por imágenes (Rx, Eco, RM, TC) y funcionales (ECG, EEG, Espirometría) relevantes para la EPC. Para cada uno captura: tipo, fecha realización, hallazgos principales y si fue normal/patológico. Solo incluye los que tuvieron impacto en la toma de decisiones clínicas.", "priority": "critica", "active": True},
            {"text": "1. FILTRO DE RELEVANCIA Y ALCANCE: Incluye EXCLUSIVAMENTE estudios por Imágenes, Endoscopias, Anatomía Patológica y Microbiología. Quedan terminalmente PROHIBIDOS los laboratorios de sangre de rutina.", "priority": "critica", "active": True},
            {"text": "2. PRECISIÓN TÉCNICA DEL INFORME: Escribe el nombre completo y exacto. Especifica técnica ('con/sin contraste'), la vía, y el lecho vascular analizado en Doppler/AngioTAC.", "priority": "alta", "active": True},
            {"text": "3. RESUMEN DE HALLAZGOS: Acompaña cada estudio con una descripción ultraconcisa de su hallazgo más relevante (Ej: 'TAC de Tórax: múltiples fracturas costales').", "priority": "alta", "active": True},
            {"text": "4. CULTIVOS Y ANATOMÍA PATOLÓGICA: Para microbiológicos, especifica sitio, germen aislado y sensibilidad. Para anatomía patológica, la conclusión macro/microscópica.", "priority": "alta", "active": True},
            {"text": "5. CRONOLOGÍA Y REPETICIONES: Enumera con su Fecha de realización estricta entre paréntesis. ELIMINA la hora. Compila repeticiones resumiendo si hubo empeoramiento.", "priority": "alta", "active": True},
            {"text": "6. ESTUDIOS FALLIDOS/SUSPENDIDOS: Si un estudio de alta relevancia no pudo completarse, súmalo a la lista indicando explícitamente el motivo de cancelación.", "priority": "normal", "active": True},
        ],
    },
    {
        "key": "interconsultas",
        "title": "Interconsultas",
        "rules": [
            {"text": "0. DEFINICIÓN CORE: Sos un médico clínico. Definí 'Interconsultas' como las evaluaciones solicitadas a otros especialistas o servicios. Incluyen IC clínicas (Cardiología, Neurología), quirúrgicas (Traumatología, Cirugía General) y de apoyo (Kinesiología, Nutrición, Salud Mental). Para cada interconsulta registrada, debes capturar ÚNICAMENTE la especialidad consultada.", "priority": "critica", "active": True},
            {"text": "1. PUREZA DE ESPECIALIDAD: Extrae únicamente valoraciones formales de especialistas externos al médico a cargo. Omite pasadas de sala del médico tratante base.", "priority": "critica", "active": True},
            {"text": "2. FORMATO MINIMALISTA ABSOLUTO: Enumera ÚNICAMENTE el nombre de la especialidad (Ej: Hematología, Infectología). Queda TERMINANTEMENTE PROHIBIDO incluir fechas, motivos, diagnósticos, resultados o conductas.", "priority": "critica", "active": True},
            {"text": "3. DEDUPLICACIÓN ESTRICTA: Agrupa cualquier repetición. Si Infectología pasó 5 veces, solo debe aparecer UNA sola vez en toda la lista.", "priority": "alta", "active": True},
            {"text": "4. PROTOCOLOS DE AISLAMIENTO: (Excepción): Si la IC resultó en un aislamiento infectológico (Ej: Aislamiento de contacto), es la ÚNICA información anexa permitida.", "priority": "alta", "active": True},
        ],
    },
    {
        "key": "medicacion",
        "title": "Medicación",
        "rules": [
            {"text": "1. SISTEMA BIPARTITO: Separa la narrativa en Medicación Habitual (pre-ingreso) y Medicación de Internación.", "priority": "critica", "active": True},
            {"text": "2. ESQUEMA FARMACOLÓGICO ABSOLUTO: Todo fármaco debe tener Nombre Genérico, Dosis, Vía y Frecuencia. Las medicaciones comerciales deben homologarse.", "priority": "alta", "active": True},
            {"text": "3. FILTRO DE RESCATES Y PROCEDIMIENTOS: Prohibido insertar procedimientos quirúrgicos aquí. Vetados los fármacos de única administración (Ringer Lactato simple, un comprimido per-don).", "priority": "critica", "active": True},
            {"text": "4. TAXONOMÍA DE RIESGO: Prioriza agrupar los antibióticos (fechas precisas del esquema), anticoagulantes, sedantes paliativos e inotrópicos.", "priority": "alta", "active": True},
            {"text": "5. CRUCES AL ALTA: Si una droga de base se suspendió, explicar por qué. La medicación de receta ambulatoria final NO va en esta sección.", "priority": "alta", "active": True},
        ],
    },
    {
        "key": "indicaciones_alta",
        "title": "Indicaciones al alta",
        "rules": [
            {"text": "1. RECETA DE EGRESO (FARMACOLOGÍA AMBULATORIA): Proporciona la lista con la que el paciente vuelve a casa (Dosis, Vía, Frecuencia). Si egresa con antibióticos, especifica cuántos días quedan.", "priority": "critica", "active": True},
            {"text": "2. TRAZABILIDAD DE ESPECIALISTAS: Detalla las citas de control exigidas y los estudios ambulatorios solicitados (indicando tiempos).", "priority": "alta", "active": True},
            {"text": "3. TERAPIA FÍSICA Y HERIDAS: Enumera las pautas sobre higiene de heridas, restricciones dietéticas y actividad física.", "priority": "alta", "active": True},
            {"text": "4. VETO PRIVACIDAD Y REPETICIONES: Elimina estrictamente teléfonos personales o de WhatsApp de médicos de esta redacción.", "priority": "critica", "active": True},
            {"text": "5. DOBLE ESCENARIO PALIATIVO/ÓBITO: En pacientes fallecidos, borrar todo e indicar hora del óbito. En pacientes paliativos, explicitar las vías de soporte domiciliario.", "priority": "alta", "active": True},
        ],
    },
    {
        "key": "recomendaciones",
        "title": "Recomendaciones médicas",
        "rules": [
            {"text": "1. PAUTAS DE ALARMA TRADUCIDAS: Escribe pautas de emergencia adaptadas a la familia que correspondan a su patología central de internación (Ej: 'Acudir a guardia ante fiebre, sangrado o pérdida de fuerza').", "priority": "critica", "active": True},
            {"text": "2. INHIBICIÓN FARMACOLÓGICA CRUZADA: Queda absolutamente PROHIBIDO repetir posologías o nombres de antibióticos aquí (eso pertenece a Indicaciones al Alta).", "priority": "critica", "active": True},
            {"text": "3. DERIVACIONES Y KINESIOLOGÍA: Si aplica internación domiciliaria o kinesiología motora de sostenimiento, plásmalo aquí.", "priority": "alta", "active": True},
            {"text": "4. DETECCIÓN DE FALLECIMIENTO: Si el documento detecta óbito, obviar todas las alarmas y generar solo: 'Paciente fallecido. Sin recomendaciones clínicas al alta'.", "priority": "critica", "active": True},
        ],
    },
    {
        "key": "obito",
        "title": "Detección de Óbito",
        "rules": [
            {"text": "Si se detecta fallecimiento, el último párrafo DEBE comenzar con: PACIENTE OBITÓ - Fecha: [fecha] Hora: [hora].", "priority": "critica", "active": True},
            {"text": "Indicaciones de alta y recomendaciones se vacían en caso de óbito.", "priority": "critica", "active": True},
            {"text": "Se eliminan frases contradictorias: 'alta médica', 'evolución favorable', 'egreso a domicilio'.", "priority": "alta", "active": True},
            {"text": "Anti-keywords (revierte, exitosa, mejoría, alta médica) invalidan la detección de muerte.", "priority": "alta", "active": True},
        ],
    },
    {
        "key": "pdf",
        "title": "Exportación PDF",
        "rules": [
            {"text": "Orden: Título, Datos clínicos, Motivo, Evolución, Procedimientos, Interconsultas, Indicaciones de alta.", "priority": "alta", "active": True},
            {"text": "Medicación, notas al alta y recomendaciones NO aparecen en el PDF.", "priority": "alta", "active": True},
        ],
    },
    {
        "key": "learned",
        "title": "Reglas aprendidas",
        "rules": [],
    },
]


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

async def _ensure_seeded(mongo):
    """Seed default rules if collection is empty."""
    count = await mongo.golden_rules.count_documents({})
    if count == 0:
        for sec in DEFAULT_SECTIONS:
            # Add IDs to rules and mark as processed
            for i, r in enumerate(sec["rules"]):
                r["id"] = f"{sec['key']}_{i+1}"
                r["processed"] = True
            await mongo.golden_rules.insert_one({
                "_id": sec["key"],
                "title": sec["title"],
                "rules": sec["rules"],
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "updated_by": "system",
            })
        log.info("[GoldenRules] Seeded %d sections", len(DEFAULT_SECTIONS))


# ──────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=List[Dict[str, Any]])
async def get_all_rules(user=Depends(get_current_user)):
    """Return all golden rule sections. Learned section includes approved dictionary mappings."""
    mongo = get_mongo_db()
    await _ensure_seeded(mongo)
    
    # Auto-migrate: ensure core exist
    for new_key, new_title in [("core", "Reglas Core")]:
        await mongo.golden_rules.update_one(
            {"_id": new_key},
            {"$setOnInsert": {"title": new_title, "rules": []}},
            upsert=True
        )
    
    # Auto-migrate: mark existing rules as processed if field missing
    async for doc in mongo.golden_rules.find({}):
        rules = doc.get("rules", [])
        needs_update = False
        for r in rules:
            if "processed" not in r:
                r["processed"] = True
                needs_update = True
        if needs_update:
            await mongo.golden_rules.update_one(
                {"_id": doc["_id"]},
                {"$set": {"rules": rules}},
            )
    
    cursor = mongo.golden_rules.find({})
    sections = []
    async for doc in cursor:
        sections.append({
            "key": doc["_id"],
            "title": doc.get("title", doc["_id"]),
            "rules": doc.get("rules", []),
            "updated_at": doc.get("updated_at"),
            "updated_by": doc.get("updated_by"),
        })
    
    # ── Merge approved dictionary mappings into "learned" section ──
    SECTION_LABELS = {
        "motivo_internacion": "Motivo internación",
        "evolucion": "Evolución",
        "procedimientos": "Procedimientos",
        "interconsultas": "Interconsultas",
        "medicacion": "Medicación",
        "indicaciones_alta": "Indicaciones alta",
        "recomendaciones": "Recomendaciones",
        "EXCLUDE": "🚫 Excluir de TODAS las secciones",
    }
    
    try:
        dict_cursor = mongo.section_mapping_dictionary.find().sort("frequency", -1).limit(200)
        
        # ── Deduplicate dictionary rules by (item_pattern, target_section) ──
        seen: dict = {}   # key = (item_upper, target) → aggregated rule
        async for doc in dict_cursor:
            item = doc.get("item_pattern", "")
            target = doc.get("target_section", "")
            freq = doc.get("frequency", 1)
            key = (item.upper().strip(), target)
            
            if key in seen:
                # Merge into existing rule
                existing = seen[key]
                existing["frequency"] += freq
                existing["audit_log"].extend(doc.get("audit_log", []))
                if doc.get("created_by") and doc["created_by"] not in existing["_contributors"]:
                    existing["_contributors"].add(doc["created_by"])
                # Keep earliest created_at
                if doc.get("created_at") and (not existing.get("created_at") or str(doc["created_at"]) < existing["created_at"]):
                    existing["created_at"] = str(doc["created_at"])
                # Keep latest updated_at
                if doc.get("updated_at") and (not existing.get("updated_at") or str(doc["updated_at"]) > existing["updated_at"]):
                    existing["updated_at"] = str(doc["updated_at"])
                # Preserve processed state
                if doc.get("processed"):
                    existing["processed"] = True
                    existing["processed_at"] = doc.get("processed_at")
                    existing["processed_by"] = doc.get("processed_by")
                
                # Aggregate from_sections
                from_sects = doc.get("from_sections", [])
                if from_sects:
                    existing.setdefault("_from_sections", set()).update(from_sects)
                    
                continue
            
            target_label = SECTION_LABELS.get(target, target)
            
            seen[key] = {
                "id": f"dict_{doc.get('_id', '')}",
                "priority": "critica" if target == "EXCLUDE" else ("alta" if freq >= 3 else "normal"),
                "active": True,
                "source": "dictionary",
                "item_pattern": item,
                "target_section": target,
                "frequency": freq,
                "created_by": doc.get("created_by", "sistema"),
                "created_at": str(doc.get("created_at", "")) if doc.get("created_at") else None,
                "updated_at": str(doc.get("updated_at", "")) if doc.get("updated_at") else None,
                "audit_log": doc.get("audit_log", []),
                "_contributors": {doc.get("created_by", "sistema")},
                "_target_label": target_label,
                "_from_sections": set(doc.get("from_sections", [])) if doc.get("from_sections") else set(),
            }
            if doc.get("processed"):
                seen[key]["processed"] = True
                seen[key]["processed_at"] = doc.get("processed_at")
                seen[key]["processed_by"] = doc.get("processed_by")
        
        # Build final dict_rules with text and contributors
        dict_rules = []
        for rule in seen.values():
            freq = rule["frequency"]
            target = rule["target_section"]
            item = rule["item_pattern"]
            target_label = rule.pop("_target_label")
            contributors = sorted(rule.pop("_contributors"))
            from_sections_set = rule.pop("_from_sections", set())
            
            # Format text explicitly (just the item)
            from_labels = [SECTION_LABELS.get(s, s) for s in sorted(from_sections_set) if s]
            
            if target == "EXCLUDE":
                text = f"🚫 '{item}'"
            else:
                text = f"'{item}'"
            
            rule["text"] = text
            rule["item_name"] = item
            rule["from_sections_labels"] = from_labels
            rule["target_section_label"] = target_label
            rule["priority"] = "critica" if target == "EXCLUDE" else ("alta" if freq >= 3 else "normal")
            rule["contributors"] = contributors
            dict_rules.append(rule)
        
        # Sort by frequency descending
        dict_rules.sort(key=lambda r: r["frequency"], reverse=True)
        
        # ── Merge into 'learned' section, removing manual duplicates ──
        # Build a set of known patterns for quick lookup
        dict_patterns = {r["item_pattern"].upper().strip() for r in dict_rules}
        
        learned = next((s for s in sections if s["key"] == "learned"), None)
        if learned:
            # Keep only manual rules that are NOT already in the dictionary
            manual_rules = []
            for r in learned["rules"]:
                if r.get("source") == "dictionary":
                    continue  # Skip old dict rules from previous loads
                # Check if this manual rule's text matches any dict pattern
                rule_text_upper = r.get("text", "").upper()
                is_dup = any(pat in rule_text_upper for pat in dict_patterns if len(pat) > 3)
                if not is_dup:
                    manual_rules.append(r)
            learned["rules"] = manual_rules + dict_rules
        elif dict_rules:
            sections.append({
                "key": "learned",
                "title": "Reglas aprendidas",
                "rules": dict_rules,
                "updated_at": None,
                "updated_by": "sistema",
            })
        
        if dict_rules:
            log.info("[GoldenRules] Merged %d deduplicated dictionary rules into 'learned' section", len(dict_rules))
    except Exception as e:
        log.warning("[GoldenRules] Could not merge dictionary rules: %s", e)
    
    # Sort by predefined order
    order = ["core", "motivo_internacion", "evolucion", "estudios", "procedimientos", "interconsultas", "learned", "medicacion", "indicaciones_alta", "recomendaciones", "obito", "pdf"]
    sections.sort(key=lambda s: order.index(s["key"]) if s["key"] in order else 99)
    
    return sections


@router.put("/{section_key}")
async def update_section_rules(
    section_key: str,
    body: RuleSectionUpdate,
    user=Depends(get_current_user),
):
    """Update rules for a specific section."""
    mongo = get_mongo_db()
    await _ensure_seeded(mongo)
    
    # Verify section exists
    existing = await mongo.golden_rules.find_one({"_id": section_key})
    if not existing:
        raise HTTPException(404, f"Sección '{section_key}' no encontrada")
    
    # Build lookup of existing rules by id to detect changes
    old_rules_map = {}
    for r in existing.get("rules", []):
        if r.get("id"):
            old_rules_map[r["id"]] = r
    
    # Only mark rules as unprocessed if they actually changed
    rules_data = []
    for i, r in enumerate(body.rules):
        rule_dict = r.dict()
        if not rule_dict.get("id"):
            rule_dict["id"] = f"{section_key}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{i}"
        
        old = old_rules_map.get(rule_dict.get("id"))
        if old is None:
            # New rule → unprocessed
            rule_dict["processed"] = False
        elif (old.get("text") != rule_dict.get("text")
              or old.get("priority") != rule_dict.get("priority")
              or old.get("active") != rule_dict.get("active")):
            # Changed rule → unprocessed
            rule_dict["processed"] = False
        else:
            # Unchanged → keep previous state
            rule_dict["processed"] = old.get("processed", True)
        
        rules_data.append(rule_dict)
    
    username = user.username if hasattr(user, 'username') else str(user)
    
    await mongo.golden_rules.update_one(
        {"_id": section_key},
        {"$set": {
            "rules": rules_data,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by": username,
        }},
    )
    
    print(f"[GoldenRules] Section '{section_key}' updated by {username}: {len(rules_data)} rules")
    
    return {"ok": True, "section": section_key, "rules_count": len(rules_data)}


@router.post("/{section_key}/add")
async def add_rule_to_section(
    section_key: str,
    rule: RuleItem,
    user=Depends(get_current_user),
):
    """Add a single rule to a section."""
    mongo = get_mongo_db()
    await _ensure_seeded(mongo)
    
    existing = await mongo.golden_rules.find_one({"_id": section_key})
    if not existing:
        raise HTTPException(404, f"Sección '{section_key}' no encontrada")
    
    rule_dict = rule.dict()
    if not rule_dict.get("id"):
        rule_dict["id"] = f"{section_key}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    rule_dict["processed"] = False
    
    username = user.username if hasattr(user, 'username') else str(user)
    
    await mongo.golden_rules.update_one(
        {"_id": section_key},
        {
            "$push": {"rules": rule_dict},
            "$set": {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "updated_by": username,
            },
        },
    )
    
    return {"ok": True, "rule_id": rule_dict["id"]}


@router.post("/{section_key}/process")
async def process_section(
    section_key: str,
    user=Depends(get_current_user),
):
    """Mark all active rules in a section as processed."""
    mongo = get_mongo_db()
    existing = await mongo.golden_rules.find_one({"_id": section_key})
    if not existing:
        raise HTTPException(404, f"Sección '{section_key}' no encontrada")
    
    username = user.username if hasattr(user, 'username') else str(user)
    now = datetime.now(timezone.utc).isoformat()
    
    # Process manual rules in golden_rules
    rules = existing.get("rules", [])
    count = 0
    for r in rules:
        if r.get("active", True):
            r["processed"] = True
            r["processed_at"] = now
            r["processed_by"] = username
            count += 1
    
    await mongo.golden_rules.update_one(
        {"_id": section_key},
        {"$set": {
            "rules": rules,
            "updated_at": now,
            "updated_by": username,
        }},
    )
    
    # If processing "learned", also mark dictionary entries as processed
    dict_count = 0
    if section_key == "learned":
        try:
            result = await mongo.section_mapping_dictionary.update_many(
                {},
                {"$set": {
                    "processed": True,
                    "processed_at": now,
                    "processed_by": username,
                }},
            )
            dict_count = result.modified_count
            log.info("[GoldenRules] Marked %d dictionary rules as processed", dict_count)
        except Exception as e:
            log.warning("[GoldenRules] Error processing dictionary rules: %s", e)
    
    log.info("[GoldenRules] Section '%s' processed by %s: %d rules + %d dict", section_key, username, count, dict_count)
    return {"ok": True, "section": section_key, "processed_count": count + dict_count}
