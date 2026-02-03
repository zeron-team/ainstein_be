# backend/app/services/ai_langchain_service.py
"""
Servicio de IA profesional basado en LangChain.
Abstrae el proveedor de LLM y facilita el cambio entre modelos.
Preparado para RAG y feedback loop.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, List
from datetime import datetime

from pydantic import BaseModel, Field

from app.core.config import settings

log = logging.getLogger(__name__)


# ============================================================================
# Output Schemas (para parseo estructurado)
# ============================================================================

class EPCGeneratedContent(BaseModel):
    """Esquema de salida para EPC generada."""
    motivo_internacion: str = Field(default="", description="Motivo de internación del paciente")
    evolucion: str = Field(default="", description="Evolución durante la internación")
    procedimientos: List[str] = Field(default_factory=list, description="Lista de procedimientos realizados")
    interconsultas: List[str] = Field(default_factory=list, description="Lista de interconsultas")
    medicacion: List[str] = Field(default_factory=list, description="Medicación administrada")
    indicaciones_alta: List[str] = Field(default_factory=list, description="Indicaciones al alta")
    recomendaciones: List[str] = Field(default_factory=list, description="Recomendaciones de seguimiento")
    diagnostico_principal: Optional[str] = Field(default=None, description="Diagnóstico principal")
    diagnosticos_secundarios: List[str] = Field(default_factory=list, description="Diagnósticos secundarios")


class PatientExtractedData(BaseModel):
    """Esquema de datos extraídos del paciente."""
    apellido: Optional[str] = None
    nombre: Optional[str] = None
    dni: Optional[str] = None
    sexo: Optional[str] = None
    fecha_nacimiento: Optional[str] = None
    obra_social: Optional[str] = None
    nro_beneficiario: Optional[str] = None
    admision_num: Optional[str] = None
    motivo_ingreso: Optional[str] = None
    cama: Optional[str] = None
    habitacion: Optional[str] = None
    protocolo: Optional[str] = None
    sector: Optional[str] = None
    diagnostico_ingreso: Optional[str] = None

# ============================================================================
# Post-Procesamiento Obligatorio de Reglas
# ============================================================================

import re

# Importar reglas centralizadas (SOLID: Single Responsibility)
try:
    from app.rules.death_detection import DeathDetectionRule, detect_death_in_text
    from app.rules.medication_classifier import classify_medication
    RULES_AVAILABLE = True
except ImportError:
    RULES_AVAILABLE = False
    log.warning("[PostProcess] Rules module not available, using fallback")

def _post_process_epc_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Post-procesa el resultado de la IA para ASEGURAR que se cumplan las reglas.
    Esta función corrige automáticamente problemas comunes que la IA puede generar.
    
    Usa el módulo centralizado de reglas (app/rules/) cuando está disponible.
    """
    if not isinstance(result, dict):
        return result
    
    evolucion = result.get("evolucion", "")
    evolucion_lower = evolucion.lower()
    
    # Detectar fallecimiento usando módulo de reglas o fallback
    if RULES_AVAILABLE:
        death_info = detect_death_in_text(evolucion)
        hay_fallecimiento = death_info.detected
        if hay_fallecimiento:
            log.info(f"[PostProcess] Fallecimiento detectado via rules module: {death_info.detection_method}")
    else:
        # Fallback: palabras clave hardcodeadas
        PALABRAS_FALLECIMIENTO = [
            "fallece", "falleció", "fallecio", "falleciendo",
            "óbito", "obito", "obitó",
            "murió", "murio", "deceso", "defunción", "defuncion", "fallecimiento",
            "paro cardiorrespiratorio", "muerte", "pcr",
            "exitus", "éxitus",
            "fin de vida",
            "se suspende soporte vital", "suspensión de soporte",
            "se certifica defunción", "certifica defunción",
            "paro cardiorrespiratorio irreversible", "pcr irreversible",
            "retiro de soporte vital", "limitación del esfuerzo terapéutico",
            "paciente finado", "finado",
            "constata", "se constata",
            "maniobras de reanimación",
            "sin respuesta a maniobras",
            "paciente fallecido"
        ]
        hay_fallecimiento = any(palabra in evolucion_lower for palabra in PALABRAS_FALLECIMIENTO)
    
    if hay_fallecimiento:
        log.info("[PostProcess] Detectado fallecimiento en evolución")
        
        # REGLA 1: Asegurar que evolución tenga el encabezado de ÓBITO con fecha correcta
        # Verificar si ya tiene el encabezado pero con fecha incompleta
        tiene_encabezado = "PACIENTE OBITÓ" in evolucion.upper()
        fecha_incompleta = "fecha no registrada" in evolucion.lower() or "fecha: no registrada" in evolucion.lower()
        
        if not tiene_encabezado or fecha_incompleta:
            # Buscar fecha y hora del fallecimiento
            fecha_obito = "fecha no registrada"
            hora_obito = "hora no registrada"
            
            # Buscar fechas en formato DD/MM/YYYY o DD/MM en todo el texto
            todas_fechas = re.findall(r'(\d{1,2}/\d{1,2}(?:/\d{4})?)', evolucion)
            
            # También buscar en procedimientos para encontrar la última fecha
            procedimientos = result.get("procedimientos", [])
            for proc in procedimientos:
                if isinstance(proc, str):
                    fechas_proc = re.findall(r'(\d{1,2}/\d{1,2}/\d{4})', proc)
                    todas_fechas.extend(fechas_proc)
            
            if todas_fechas:
                # Tomar la ÚLTIMA fecha (más probable que sea la del fallecimiento)
                fecha_obito = todas_fechas[-1]
                # Si no tiene año, agregar año
                if fecha_obito.count('/') == 1:
                    fecha_obito = fecha_obito + "/2025"
            
            # Buscar hora cerca del fallecimiento
            hora_patterns = [
                r'(?:fallec\w+|murió?|deceso|paro|pcr|obito)[^.]*?(\d{1,2}:\d{2})',
                r'(\d{1,2}:\d{2})\s*(?:hs|hrs|horas)',
                r'a las\s*(\d{1,2}:\d{2})',
            ]
            for pattern in hora_patterns:
                hora_match = re.search(pattern, evolucion_lower)
                if hora_match:
                    hora_obito = hora_match.group(1)
                    break
            
            # Si ya tiene encabezado pero fecha incompleta, reemplazar
            if fecha_incompleta and tiene_encabezado:
                # Reemplazar la línea existente
                evolucion = re.sub(
                    r'PACIENTE OBITÓ\s*-\s*Fecha:\s*(?:no registrada|fecha no registrada)',
                    f'PACIENTE OBITÓ - Fecha: {fecha_obito}',
                    evolucion,
                    flags=re.IGNORECASE
                )
                result["evolucion"] = evolucion
                log.info(f"[PostProcess] Corregida fecha de óbito: {fecha_obito}")
            else:
                # Agregar encabezado nuevo
                parrafos = evolucion.split("\n\n")
                
                # Buscar el párrafo que contiene el fallecimiento
                idx_fallecimiento = -1
                for i, p in enumerate(parrafos):
                    # Usar reglas module si disponible
                    if RULES_AVAILABLE:
                        death_check = detect_death_in_text(p)
                        if death_check.detected:
                            idx_fallecimiento = i
                    else:
                        p_lower = p.lower()
                        death_kws = ["fallece", "óbito", "obito", "constata", "murió", "paro cardio"]
                        if any(kw in p_lower for kw in death_kws):
                            idx_fallecimiento = i
                
                if idx_fallecimiento == -1:
                    idx_fallecimiento = len(parrafos) - 1
                
                ultimo_parrafo = parrafos[idx_fallecimiento]
                nuevo_ultimo = f"PACIENTE OBITÓ - Fecha: {fecha_obito} Hora: {hora_obito}. {ultimo_parrafo}"
                
                parrafos[idx_fallecimiento] = nuevo_ultimo
                result["evolucion"] = "\n\n".join(parrafos)
                
                log.info(f"[PostProcess] Agregado encabezado PACIENTE OBITÓ - Fecha: {fecha_obito} Hora: {hora_obito}")
        
        # REGLA 2: Vaciar indicaciones de alta si hay fallecimiento
        if result.get("indicaciones_alta"):
            result["indicaciones_alta"] = []
            log.info("[PostProcess] Vaciadas indicaciones_alta por fallecimiento")
        
        # REGLA 3: Vaciar recomendaciones si hay fallecimiento
        if result.get("recomendaciones"):
            result["recomendaciones"] = []
            log.info("[PostProcess] Vaciadas recomendaciones por fallecimiento")
        
        # =====================================================================
        # REGLA 3.5: ELIMINAR FRASES CONTRADICTORIAS DE ALTA cuando hay óbito
        # El LLM a veces genera "PACIENTE OBITÓ" pero luego dice "se decide alta"
        # Esto es crítico: NO puede haber mención de alta si el paciente falleció
        # =====================================================================
        frases_alta_contradictoria = [
            # Variaciones de "se retira"
            r"(?:se retira|paciente se retira|retirándose)\s+(?:deambulando|caminando|por sus propios medios)",
            # Variaciones de "es dado de alta"
            r"(?:es dado|es dada|fue dado|fue dada)\s+de alta",
            # Alta con deambulación
            r"alta (?:médica|hospitalaria)\s*[,.]?\s*(?:retirándose|deambulando|por sus propios medios)",
            # "se decide alta" (cualquier variación)
            r"se decide\s+(?:el\s+)?alta(?:\s+a domicilio)?",
            r"(?:alta|egreso)\s+a\s+domicilio",
            # "evolución favorable" + alta
            r"evolucion(?:ó|a)?\s+favorablemente[^.]*(?:alta|retir|egres)",
            r"favorable\s+evolución[^.]*(?:alta|retir|egres)",
            # ⚠️ NUEVO: "evolucionó sintomáticamente favorable" (sin mencionar alta)
            r"evolucion(?:ó|a)?\s+sintomáticamente\s+favorable",
            r"evolución?\s+sintomática\s+favorable",
            # ⚠️ NUEVO: "la paciente evoluciona favorablemente" (sin mencionar alta)
            r"(?:la\s+)?paciente\s+(?:evoluciona|evolucionó)\s+favorablemente",
            r"(?:evoluciona|evolucionó)\s+favorablemente",
            # ⚠️ NUEVO: "buena respuesta al tratamiento, se da de alta"
            r"buena respuesta al tratamiento[^.]*(?:se da|alta|egres)",
            # "buena evolución" + alta/retira
            r"buena evolución[^.]*(?:se retira|alta|egres)",
            r"(?:paciente|pte)\s+con\s+buena evolución[^.]*(?:se retira|alta|egres)",
            # "mejoría" + alta
            r"(?:mejoría|mejoria)\s+[^.]*(?:se decide|alta|egres)",
            # "respuesta al tratamiento" + alta
            r"respuesta\s+al\s+tratamiento[^.]*(?:alta|egres)",
            # Menciones genéricas de alta exitosa
            r"(?:recibe|obtiene|se otorga)\s+(?:el\s+)?alta",
            r"alta\s+(?:médica|médico|medica|hospitalaria)",
            # "se va/retira/egresa" variations
            r"(?:paciente|pte)\s+(?:se va|egresa|retira)\s+(?:del|de la)?\s*(?:hospital|institución|clínica|nosocomio)?",
            # ⚠️ NUEVO: "se da de alta" genérico
            r"se da de alta",
            # "paciente de alta" / "paciente con alta"
            r"(?:el\s+)?paciente\s+(?:de|con)\s+alta",
            r"(?:el\s+)?paciente\s+se\s+va\s+de\s+alta",
            # Controles ambulatorios (indicador fuerte de alta)
            r"controles\s+ambulatorios",
            r"seguimiento\s+ambulatorio",
            r"control\s+por\s+consultorio",
            r"se\s+otorga\s+(?:el\s+)?egreso",
            r"egreso\s+(?:sanatorial|hospitalario)",
            r"alta\s+sanatorial",
        ]
        
        evolucion = result.get("evolucion", "")
        evolucion_modificada = evolucion
        frases_eliminadas = 0
        
        for patron in frases_alta_contradictoria:
            if re.search(patron, evolucion_modificada, re.IGNORECASE):
                log.info(f"[PostProcess] Detectada frase contradictoria de alta: {patron}")
                # Eliminar la oración completa que contiene la contradicción
                # Buscar desde el punto anterior hasta el punto siguiente
                evolucion_modificada = re.sub(
                    r'[^.]*' + patron + r'[^.]*\.?\s*',
                    '',
                    evolucion_modificada,
                    flags=re.IGNORECASE
                )
                frases_eliminadas += 1
        
        # Si se eliminaron frases, verificar que el resultado sea usable
        # Condición más relajada: mínimo 30 caracteres O que contenga la marca de óbito
        if frases_eliminadas > 0:
            texto_limpio = evolucion_modificada.strip()
            # Limpiar espacios múltiples y saltos de línea extras
            texto_limpio = re.sub(r'\s+', ' ', texto_limpio)
            texto_limpio = re.sub(r'\.\s+\.', '.', texto_limpio)
            
            tiene_obito_marker = any(m in texto_limpio.upper() for m in ["PACIENTE OBITÓ", "PACIENTE OBITO", "⚫ PACIENTE"])
            
            if len(texto_limpio) > 30 or tiene_obito_marker:
                result["evolucion"] = evolucion_modificada.strip()
                log.info(f"[PostProcess] Eliminadas {frases_eliminadas} frases contradictorias de alta por fallecimiento")
            else:
                log.warning("[PostProcess] Se detectaron frases contradictorias pero el texto quedaría muy corto - manteniendo original")
        
        # =====================================================================
    
    # =========================================================================
    # REGLA 4: Filtrar interconsultas sin fecha y normalizar formato
    # =========================================================================
    def tiene_fecha(texto: str) -> bool:
        """Verifica si el texto tiene fecha en cualquier formato."""
        # Formato DD/MM/YYYY
        if re.search(r'\d{1,2}/\d{1,2}/\d{4}', texto):
            return True
        # Formato YYYY-MM-DD
        if re.search(r'\d{4}-\d{2}-\d{2}', texto):
            return True
        return False
    
    def normalizar_fecha(texto: str) -> str:
        """Convierte YYYY-MM-DD a DD/MM/YYYY."""
        def reemplazar(match):
            year, month, day = match.group(1), match.group(2), match.group(3)
            return f"{day}/{month}/{year}"
        return re.sub(r'(\d{4})-(\d{2})-(\d{2})', reemplazar, texto)
    
    interconsultas = result.get("interconsultas", [])
    if interconsultas and isinstance(interconsultas, list):
        interconsultas_validas = []
        for ic in interconsultas:
            if isinstance(ic, str):
                if tiene_fecha(ic):
                    # Normalizar formato de fecha
                    ic_normalizado = normalizar_fecha(ic)
                    interconsultas_validas.append(ic_normalizado)
                else:
                    log.warning(f"[PostProcess] Eliminada interconsulta sin fecha: {ic}")
        result["interconsultas"] = interconsultas_validas
        log.info(f"[PostProcess] Interconsultas procesadas: {len(interconsultas_validas)} válidas")
    
    # =========================================================================
    # REGLA 5: Filtrar procedimientos sin fecha y normalizar formato
    # =========================================================================
    procedimientos = result.get("procedimientos", [])
    if procedimientos and isinstance(procedimientos, list):
        procedimientos_validos = []
        hemodialisis_fechas = []
        
        for proc in procedimientos:
            if isinstance(proc, str):
                if tiene_fecha(proc):
                    # Normalizar formato de fecha
                    proc_normalizado = normalizar_fecha(proc)
                    
                    # Detectar hemodiálisis para agrupar
                    if "hemodiálisis" in proc_normalizado.lower() or "hemodialisis" in proc_normalizado.lower():
                        # Extraer solo la fecha para agrupar
                        fecha_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', proc_normalizado)
                        if fecha_match:
                            hemodialisis_fechas.append(fecha_match.group(1))
                    else:
                        procedimientos_validos.append(proc_normalizado)
                else:
                    log.warning(f"[PostProcess] Eliminado procedimiento sin fecha: {proc}")
        
        # Agrupar hemodiálisis si hay múltiples
        if len(hemodialisis_fechas) > 1:
            # Parsear fechas para ordenar
            from datetime import datetime
            fechas_ordenadas = sorted(hemodialisis_fechas, key=lambda x: datetime.strptime(x, "%d/%m/%Y"))
            primera_fecha = fechas_ordenadas[0]
            ultima_fecha = fechas_ordenadas[-1]
            cantidad = len(fechas_ordenadas)
            
            # Crear entrada agrupada
            hemodialisis_agrupada = f"{primera_fecha} - Hemodiálisis ({cantidad} sesiones del {primera_fecha} al {ultima_fecha})"
            procedimientos_validos.append(hemodialisis_agrupada)
            log.info(f"[PostProcess] Agrupadas {cantidad} sesiones de hemodiálisis")
        elif len(hemodialisis_fechas) == 1:
            # Solo una hemodiálisis, mantener individual
            procedimientos_validos.append(f"{hemodialisis_fechas[0]} - Hemodiálisis")
        
        result["procedimientos"] = procedimientos_validos
        log.info(f"[PostProcess] Procedimientos procesados: {len(procedimientos_validos)} válidos")
    
    # =========================================================================
    # REGLA 4: Verificar y corregir clasificación de medicación
    # =========================================================================
    medicacion = result.get("medicacion", [])
    if medicacion and isinstance(medicacion, list):
        # Medicamentos típicamente PREVIOS (tratamiento crónico)
        MEDICAMENTOS_TIPICOS_PREVIOS = [
            # Antihipertensivos
            "losartan", "valsartan", "enalapril", "lisinopril", "amlodipino", "amlodipina",
            "carvedilol", "atenolol", "metoprolol", "bisoprolol", "propranolol",
            # Estatinas (SOLO estas porque siempre son crónicos)
            "atorvastatin", "atorvastatina", "simvastatin", "rosuvastatina",
            # Diabetes
            "metformina", "glibenclamida", "sitagliptina", "dapagliflozina",
            # Tiroides
            "levotiroxina", "t4",
            # Otros crónicos que SIEMPRE son previos
            "cilostazol",
        ]
        
        # Medicamentos que NO se deben reclasificar (pueden ser previos O internación)
        NO_RECLASIFICAR = [
            "aspirina", "ácido acetilsalicílico", "acetilsalicilico", "aas",
            "clopidogrel", "warfarina", "acenocumarol",
            "omeprazol", "esomeprazol", "pantoprazol", "lansoprazol",
        ]
        
        # Medicamentos típicamente de INTERNACIÓN (tratamiento agudo)
        MEDICAMENTOS_TIPICOS_INTERNACION = [
            # Antibióticos IV
            "ampicilina", "sulbactam", "piperacilina", "tazobactam", "vancomicina",
            "meropenem", "ceftriaxona", "ceftazidima", "ciprofloxacina", "metronidazol",
            "cotrimoxazol",
            # Analgésicos/sedantes
            "morfina", "fentanilo", "tramadol", "naloxona", "haloperidol", "midazolam",
            # Soporte
            "furosemida", "noradrenalina", "dobutamina", "dopamina", "vasopresina",
            # Otros agudos
            "amiodarona",  # cuando se usa para cardioversión
            "heparina", "enoxaparina",
        ]
        
        medicacion_corregida = []
        for med in medicacion:
            if not isinstance(med, dict):
                continue
            
            farmaco = med.get("farmaco", "").lower()
            tipo_actual = med.get("tipo", "").lower()
            
            # Verificar si necesita corrección
            nuevo_tipo = tipo_actual
            
            # Verificar si este medicamento no se debe reclasificar (puede ser previo O internación)
            no_reclasificar = any(nr in farmaco for nr in NO_RECLASIFICAR)
            
            # Chequear contra listas de referencia
            es_tipico_previo = any(mp in farmaco for mp in MEDICAMENTOS_TIPICOS_PREVIOS)
            es_tipico_internacion = any(mi in farmaco for mi in MEDICAMENTOS_TIPICOS_INTERNACION)
            
            # Solo reclasificar si NO está en la lista de NO_RECLASIFICAR
            if not no_reclasificar:
                if es_tipico_previo and tipo_actual == "internacion":
                    # Posible error: medicamento crónico marcado como internación
                    # Solo corregir si es muy probable que sea previo
                    via = med.get("via", "").lower()
                    if via == "oral" or via == "vo":
                        nuevo_tipo = "previa"
                        log.info(f"[PostProcess] Corregido {farmaco}: internacion -> previa (crónico oral)")
                
                elif es_tipico_internacion and tipo_actual == "previa":
                    # Posible error: medicamento agudo marcado como previo
                    via = med.get("via", "").lower()
                    if via in ["iv", "intravenoso", "ev", "endovenoso"]:
                        nuevo_tipo = "internacion"
                        log.info(f"[PostProcess] Corregido {farmaco}: previa -> internacion (agudo IV)")
            
            # Si no tiene tipo, asignar basándose en patrones
            if not tipo_actual:
                if es_tipico_previo:
                    nuevo_tipo = "previa"
                elif es_tipico_internacion:
                    nuevo_tipo = "internacion"
                else:
                    # Por defecto, asumir internación si no se puede determinar
                    nuevo_tipo = "internacion"
                log.info(f"[PostProcess] Asignado tipo {nuevo_tipo} a {farmaco}")
            
            med["tipo"] = nuevo_tipo
            medicacion_corregida.append(med)
        
        # REGLA 6: Ordenar medicación alfabéticamente por nombre de fármaco
        medicacion_corregida.sort(key=lambda m: m.get("farmaco", "").lower())
        
        result["medicacion"] = medicacion_corregida
        log.info(f"[PostProcess] Medicación verificada y ordenada: {len(medicacion_corregida)} items")
    
    return result


# ============================================================================
# LangChain AI Service
# ============================================================================

class LangChainAIService:
    """
    Servicio de IA basado en LangChain.
    
    Beneficios:
    - Abstracción del LLM (cambiar Gemini → OpenAI sin refactor)
    - Prompt templates versionados
    - Output parsers tipados
    - Preparado para RAG y feedback loop
    """
    
    def __init__(
        self,
        model: Optional[str] = None,
        temperature: float = 0.3,
    ):
        self.model_name = model or settings.GEMINI_MODEL or "gemini-2.0-flash"
        self.temperature = temperature
        self._llm = None
        self._initialized = False
    
    def _initialize(self):
        """Inicialización lazy del LLM."""
        if self._initialized:
            return
        
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            
            self._llm = ChatGoogleGenerativeAI(
                model=self.model_name,
                google_api_key=settings.GEMINI_API_KEY,
                temperature=self.temperature,
                convert_system_message_to_human=True,
            )
            self._initialized = True
            log.info("[LangChainAI] Initialized with model: %s", self.model_name)
            
        except ImportError:
            log.warning("[LangChainAI] langchain-google-genai not installed, falling back")
            raise RuntimeError("LangChain dependencies not installed")
    
    @property
    def llm(self):
        """Acceso lazy al LLM."""
        if not self._initialized:
            self._initialize()
        return self._llm
    
    async def generate_epc(
        self,
        hce_text: str,
        pages: int = 0,
        feedback_examples: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Genera contenido de EPC usando LangChain.
        
        FERRO D2: Traced for observability.
        
        Args:
            hce_text: Texto de la HCE
            pages: Número de páginas (para contexto)
            feedback_examples: Ejemplos de EPCs exitosas para few-shot learning
        
        Returns:
            Diccionario con contenido generado y metadatos
        """
        # FERRO D2: Start span for LLM generation
        from app.core.telemetry import get_tracer
        tracer = get_tracer()
        
        span_ctx = tracer.start_as_current_span("llm.generate") if tracer else None
        if span_ctx:
            span = span_ctx.__enter__()
            span.set_attribute("model", self.model_name)
            span.set_attribute("input_length", len(hce_text))
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import JsonOutputParser
        
        # Obtener reglas de feedback insights (aprendizaje continuo)
        feedback_rules = ""
        try:
            from app.services.feedback_insights_service import get_prompt_rules
            feedback_rules = await get_prompt_rules()
            if feedback_rules:
                log.info("[LangChainAI] Using %d chars of feedback insights rules", len(feedback_rules))
        except Exception as e:
            log.warning("[LangChainAI] Could not get feedback insights: %s", e)
        
        # Construir prompt con template
        system_prompt = self._get_epc_system_prompt()
        
        # Agregar reglas de feedback al system prompt
        if feedback_rules:
            system_prompt = system_prompt + feedback_rules
        
        # Few-shot examples si hay feedback disponible
        examples_text = ""
        if feedback_examples:
            examples_text = self._format_feedback_examples(feedback_examples)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", self._get_epc_user_prompt(examples_text)),
        ])
        
        # Parser de salida JSON
        parser = JsonOutputParser(pydantic_object=EPCGeneratedContent)
        
        # Chain: prompt → LLM → parser
        chain = prompt | self.llm | parser
        
        try:
            result = await chain.ainvoke({
                "hce_text": hce_text,
                "pages": pages,
                "examples": examples_text,
            })
            
            try:
                from app.services.llm_usage_tracker import get_llm_usage_tracker
                tracker = get_llm_usage_tracker()
                
                # Estimar tokens (LangChain con Gemini no da usage directo)
                # Aproximación: 1 token ≈ 4 caracteres
                input_tokens = len(hce_text + system_prompt + examples_text) // 4
                output_tokens = len(str(result)) // 4
                
                await tracker.track_usage(
                    operation_type="epc_generation",
                    model=self.model_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    metadata={"pages": pages, "has_examples": bool(feedback_examples)},
                )
            except Exception as track_err:
                log.warning("[LangChainAI] Failed to track usage: %s", track_err)
            
            # ⚠️ POST-PROCESAMIENTO OBLIGATORIO: Asegurar cumplimiento de reglas
            result = _post_process_epc_result(result)
            log.info("[LangChainAI] Post-procesamiento de reglas aplicado")
            
            return {
                "json": result,
                "_provider": "langchain",
                "_model": self.model_name,
                "_generated_at": datetime.utcnow().isoformat(),
                "_feedback_insights_used": bool(feedback_rules),
                "_post_processed": True,
            }
            
        except Exception as e:
            log.error("[LangChainAI] Error generating EPC: %s", e)
            raise RuntimeError(f"Error generando EPC: {e}") from e
    
    async def extract_patient_data(self, hce_text: str) -> Dict[str, Any]:
        """Extrae datos demográficos del paciente desde HCE."""
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import JsonOutputParser
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", self._get_patient_extraction_prompt()),
            ("human", "Texto de HCE:\n\n{hce_text}"),
        ])
        
        parser = JsonOutputParser(pydantic_object=PatientExtractedData)
        chain = prompt | self.llm | parser
        
        result = await chain.ainvoke({"hce_text": hce_text})
        return result
    
    def _get_epc_system_prompt(self) -> str:
        """Prompt de sistema para generación de EPC."""
        return """Eres un médico especialista en redacción de Epicrisis (EPC) hospitalarias.
Tu tarea es generar una EPC profesional, completa y precisa basándote en el texto de la Historia Clínica Electrónica (HCE).

################################################################################
#                                                                              #
#   ⛔ REGLAS OBLIGATORIAS - INCUMPLIRLAS ES UN ERROR CRÍTICO ⛔              #
#                                                                              #
################################################################################

REGLA GENERAL #1: SOLO usa información presente en el texto de la HCE. NO inventes datos.
REGLA GENERAL #2: Si una sección no tiene información, deja el campo vacío o como lista vacía.
REGLA GENERAL #3: Responde ÚNICAMENTE con JSON válido.

================================================================================
📋 SECCIÓN: EVOLUCIÓN - REGLAS OBLIGATORIAS
================================================================================

⛔⛔⛔ REGLA CRÍTICA DE FALLECIMIENTO/ÓBITO - NO NEGOCIABLE ⛔⛔⛔

Esta es la regla MÁS IMPORTANTE de todas. DEBES verificarla ANTES de generar la respuesta.

Si en CUALQUIER parte del texto aparece que el paciente:
- "fallece", "falleció", "fallecio", "falleciendo"
- "óbito", "obito", "obitó", "éxitus", "exitus"
- "murió", "murio", "deceso", "defunción", "defuncion"
- "fin de vida", "finado"
- "paro cardiorrespiratorio" (en tiempo pasado o definitivo)
- "se suspende soporte vital", "se certifica defunción"
- "retiro de soporte", "limitación del esfuerzo terapéutico" + indicación de muerte
- "pcr irreversible"
- CUALQUIER indicación explícita o implícita de muerte del paciente

ENTONCES el ÚLTIMO PÁRRAFO de "evolucion" OBLIGATORIAMENTE DEBE comenzar con:

"PACIENTE OBITÓ - Fecha: [fecha del fallecimiento] Hora: [hora o 'hora no registrada']. [descripción de las circunstancias]"

⚠️ IMPORTANTE: Busca la FECHA y HORA del fallecimiento en el texto. Si no está explícita, usa la última fecha mencionada.

EJEMPLO CORRECTO 1:
"PACIENTE OBITÓ - Fecha: 15/03/2025 Hora: 14:30. Evolucionó con shock séptico refractario a vasopresores."

EJEMPLO CORRECTO 2:
"PACIENTE OBITÓ - Fecha: 22/07/2025 Hora: hora no registrada. Presentó paro cardiorrespiratorio irreversible en contexto de falla multiorgánica."

EJEMPLOS INCORRECTOS (NUNCA HACER ESTO):
❌ "Evoluciona desfavorablemente y fallece."
❌ "Paciente presenta óbito el día 15/03."
❌ "Finalmente el paciente muere."

NO OMITIR ESTA REGLA BAJO NINGUNA CIRCUNSTANCIA.
SI DETECTAS FALLECIMIENTO, ESTA REGLA TIENE PRIORIDAD ABSOLUTA SOBRE CUALQUIER OTRA.

================================================================================
📋 SECCIÓN: PROCEDIMIENTOS - REGLAS OBLIGATORIAS
================================================================================

FORMATO OBLIGATORIO:
"DD/MM/YYYY HH:MM - Descripción" (con hora)
"DD/MM/YYYY (hora no registrada) - Descripción" (sin hora)

⛔ FORMATO DE FECHA: USAR SIEMPRE DD/MM/YYYY (ejemplo: 10/07/2025)
⛔ NUNCA usar formato YYYY-MM-DD (ejemplo: 2025-07-10) - ESTO ES UN ERROR

⛔ REGLAS CRÍTICAS:
1. EXTRAER TODOS los procedimientos mencionados en la HCE, sin omitir ninguno
2. NUNCA escribir procedimiento sin fecha
3. ELIMINAR solo duplicados EXACTOS
4. ORDENAR cronológicamente (fecha más antigua primero)

⚠️ LABORATORIOS - INSTRUCCIONES ESPECÍFICAS:
Los estudios de laboratorio son procedimientos y DEBEN incluirse.
Buscar en la HCE menciones de:
- Hemograma, glucemia, creatinina, uremia, ionograma, hepatograma
- Coagulograma, gasometría, ácido láctico, calcemia, magnesio
- Hemocultivos, urocultivos, hisopados
- CUALQUIER análisis de sangre u orina

Para cada solicitud de laboratorio encontrada, crear UNA entrada:
"DD/MM/YYYY HH:MM - Laboratorio: [lista de estudios solicitados]"

Ejemplo: "10/07/2025 08:00 - Laboratorio: hemograma, glucemia, creatinina, ionograma"

⚠️ ESTUDIOS POR IMÁGENES:
Incluir TODOS: radiografías, TAC, ecografías, ecodoppler, resonancias.
"DD/MM/YYYY (hora no registrada) - Rx tórax frente"
"DD/MM/YYYY (hora no registrada) - TAC cerebro sin contraste"

⚠️ PROCEDIMIENTOS INVASIVOS:
Incluir TODOS: colocación de vías, sondas, catéteres, intubación, diálisis.

================================================================================
📋 SECCIÓN: INTERCONSULTAS - REGLAS OBLIGATORIAS
================================================================================
FORMATO OBLIGATORIO:
"DD/MM/YYYY HH:MM - Especialidad" (con hora)
"DD/MM/YYYY (hora no registrada) - Especialidad" (sin hora)

⛔ REGLAS CRÍTICAS:
1. EXTRAER TODAS las interconsultas mencionadas
2. NUNCA escribir interconsulta sin fecha
3. ELIMINAR duplicados exactos (misma fecha + misma especialidad)
4. ORDENAR cronológicamente (fecha más antigua primero)

================================================================================
📋 SECCIÓN: MEDICACIÓN - REGLAS OBLIGATORIAS
================================================================================

FORMATO OBLIGATORIO JSON:
{{"tipo": "internacion" | "previa", "farmaco": "nombre", "dosis": "cantidad", "via": "IV|Oral|SC|IM", "frecuencia": "cada X hs"}}

⛔ CLASIFICACIÓN OBLIGATORIA:

"previa" = medicación que el paciente YA TOMABA ANTES de ingresar:
- Buscar en: "antecedentes", "medicación habitual", "tratamiento crónico", "toma habitualmente"
- SIEMPRE son "previa" (si son orales y aparecen en antecedentes):
  • Valsartan, Losartan, Enalapril, Amlodipino (antihipertensivos)
  • Cilostazol, Aspirina, Clopidogrel (antiagregantes)
  • Atorvastatina, Rosuvastatina (estatinas)
  • Metformina, Glibenclamida (diabetes)
  • Levotiroxina (tiroides)
  • Omeprazol, Pantoprazol (IBP)

"internacion" = medicación INDICADA DURANTE la hospitalización:
- Buscar en: "indicaciones médicas", "plan terapéutico", "se inicia", "se indica"
- SIEMPRE son "internacion" (si son IV o se inician durante internación):
  • Ampicilina/Sulbactam, Piperacilina/Tazobactam, Vancomicina (ATB)
  • Morfina, Fentanilo, Tramadol IV (analgésicos)
  • Noradrenalina, Dopamina, Dobutamina (vasopresores)
  • Haloperidol, Midazolam, Propofol (sedantes/antipsicóticos)
  • Furosemida IV, Amiodarona IV (soporte)
  • Solución fisiológica, Dextrosa, Ringer (cristaloides)
  • Heparina, Enoxaparina (anticoagulantes)

⛔ REGLA CRÍTICA DE CLASIFICACIÓN:
1. Si el medicamento aparece en ANTECEDENTES → tipo = "previa"
2. Si el medicamento se INDICA durante la internación → tipo = "internacion"
3. Un medicamento puede aparecer en AMBAS si se menciona en ambos contextos
4. ORDENAR la lista de medicación ALFABÉTICAMENTE por nombre del fármaco

================================================================================
📋 SECCIÓN: INDICACIONES AL ALTA - REGLAS OBLIGATORIAS
================================================================================
- Si el paciente FALLECIÓ, esta sección DEBE estar VACÍA []
- No dar indicaciones de alta a un paciente fallecido

================================================================================
📋 SECCIÓN: RECOMENDACIONES - REGLAS OBLIGATORIAS
================================================================================
- Si el paciente FALLECIÓ, esta sección DEBE estar VACÍA []
- No dar recomendaciones a un paciente fallecido

################################################################################
ESTRUCTURA DE RESPUESTA (JSON):
################################################################################
{{
  "motivo_internacion": "string",
  "evolucion": "string (⛔ si hay fallecimiento, el último párrafo DEBE comenzar con 'PACIENTE OBITÓ - Fecha: ...')",
  "procedimientos": ["DD/MM/YYYY HH:MM - Descripción"],
  "interconsultas": ["DD/MM/YYYY HH:MM - Especialidad"],
  "medicacion": [
    {{"tipo": "internacion|previa", "farmaco": "nombre", "dosis": "cantidad", "via": "IV|Oral|SC|IM", "frecuencia": "cada X hs"}}
  ],
  "indicaciones_alta": ["string (VACÍO si paciente falleció)"],
  "recomendaciones": ["string (VACÍO si paciente falleció)"],
  "diagnostico_principal": "string | null",
  "diagnosticos_secundarios": ["string"]
}}"""
    
    def _get_epc_user_prompt(self, examples_text: str = "") -> str:
        """Prompt de usuario para generación de EPC."""
        base = """Genera la Epicrisis basándote en la siguiente HCE ({pages} páginas):

{hce_text}"""
        
        if examples_text:
            base = f"""Aquí hay ejemplos de EPCs bien calificadas por usuarios:

{examples_text}

---

{base}"""
        
        return base
    
    def _get_patient_extraction_prompt(self) -> str:
        """Prompt para extracción de datos de paciente."""
        return """Eres un experto extrayendo datos de Historias Clínicas Electrónicas.
Analiza el texto y extrae los datos demográficos del paciente.

Responde SOLO con JSON válido con esta estructura:
{{
  "apellido": "string | null",
  "nombre": "string | null", 
  "dni": "string | null",
  "sexo": "Masculino | Femenino | null",
  "fecha_nacimiento": "YYYY-MM-DD | null",
  "obra_social": "string | null",
  "nro_beneficiario": "string | null",
  "admision_num": "string | null",
  "motivo_ingreso": "string | null",
  "cama": "string | null",
  "habitacion": "string | null",
  "protocolo": "string | null",
  "sector": "string | null",
  "diagnostico_ingreso": "string | null"
}}"""
    
    def _format_feedback_examples(self, examples: List[Dict[str, Any]]) -> str:
        """Formatea ejemplos de feedback para few-shot learning."""
        if not examples:
            return ""
        
        formatted = []
        for i, ex in enumerate(examples[:3], 1):  # Máximo 3 ejemplos
            formatted.append(f"""Ejemplo {i}:
Sección: {ex.get('section', 'unknown')}
Contenido exitoso: {ex.get('original_content', '')[:500]}
""")
        
        return "\n".join(formatted)


# ============================================================================
# Factory function (para mantener compatibilidad)
# ============================================================================

def get_ai_service(use_langchain: bool = True) -> Any:
    """
    Factory para obtener el servicio de IA apropiado.
    
    Args:
        use_langchain: Si True, usa LangChain. Si False, usa servicio legacy.
    
    Returns:
        Instancia del servicio de IA
    """
    if use_langchain:
        try:
            return LangChainAIService()
        except Exception as e:
            log.warning("[get_ai_service] LangChain failed, falling back to legacy: %s", e)
    
    # Fallback al servicio legacy
    from app.services.ai_gemini_service import GeminiAIService
    return GeminiAIService()
