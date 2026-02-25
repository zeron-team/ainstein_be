# backend/app/services/ai_llamaindex_service.py
"""
Servicio de IA profesional basado en LlamaIndex (FERRO D2 v4).
Migrado desde LangChain para arquitectura Data-Centric.

MANTIENE LA MISMA INTERFAZ que ai_langchain_service.py:
- generate_epc()
- extract_patient_data()
- get_ai_service()
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional, List
from datetime import datetime

from pydantic import BaseModel, Field

from app.core.config import settings

log = logging.getLogger(__name__)


# ============================================================================
# Output Schemas (sin cambios - compatibilidad con LangChain)
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
# Importar post-procesamiento desde servicio original (sin cambios)
# ============================================================================
from app.services.ai_langchain_service import _post_process_epc_result


# ============================================================================
# LlamaIndex AI Service
# ============================================================================

class LlamaIndexAIService:
    """
    Servicio de IA basado en LlamaIndex (FERRO D2 v4).
    
    Beneficios sobre LangChain:
    - Arquitectura Data-Centric con índices declarativos
    - IngestionPipeline para procesamiento de documentos
    - QueryEngine para recuperación semántica
    - Mejor integración con vector stores
    
    MISMA INTERFAZ que LangChainAIService para migración transparente.
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
            from llama_index.llms.gemini import Gemini
            
            self._llm = Gemini(
                model=f"models/{self.model_name}",
                api_key=settings.GEMINI_API_KEY,
                temperature=self.temperature,
            )
            self._initialized = True
            log.info("[LlamaIndexAI] Initialized with model: %s", self.model_name)
            
        except ImportError:
            log.warning("[LlamaIndexAI] llama-index-llms-gemini not installed")
            raise RuntimeError("LlamaIndex dependencies not installed")
    
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
        similar_context: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Genera contenido de EPC usando LlamaIndex.
        
        FERRO D2 v4: Data-Centric approach with LlamaIndex + RAG.
        
        Args:
            hce_text: Texto de la HCE
            pages: Número de páginas (para contexto)
            feedback_examples: Ejemplos de EPCs exitosas para few-shot learning
            similar_context: Chunks similares de otras HCEs (RAG retrieval)
        
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
            span.set_attribute("framework", "llamaindex")
        
        # Obtener reglas de feedback insights (aprendizaje continuo)
        feedback_rules = ""
        try:
            from app.services.feedback_insights_service import get_prompt_rules
            feedback_rules = await get_prompt_rules()
            if feedback_rules:
                log.info("[LlamaIndexAI] Using %d chars of feedback insights rules", len(feedback_rules))
        except Exception as e:
            log.warning("[LlamaIndexAI] Could not get feedback insights: %s", e)
        
        # Construir prompt con template
        system_prompt = self._get_epc_system_prompt()
        
        # Agregar reglas de feedback al system prompt
        if feedback_rules:
            system_prompt = system_prompt + feedback_rules
        
        # Few-shot examples si hay feedback disponible
        examples_text = ""
        if feedback_examples:
            examples_text = self._format_feedback_examples(feedback_examples)
        
        # RAG context: chunks similares de otras HCEs
        rag_context_text = ""
        if similar_context:
            rag_parts = []
            for ctx in similar_context[:3]:  # Máximo 3 chunks
                text = ctx.get("text", ctx.get("content", ""))
                score = ctx.get("score", 0)
                if text:
                    rag_parts.append(f"[Similitud: {score:.2f}] {text[:800]}")
            if rag_parts:
                rag_context_text = (
                    "\n\n--- CONTEXTO DE CASOS SIMILARES (RAG) ---\n"
                    + "\n---\n".join(rag_parts)
                    + "\n--- FIN CONTEXTO RAG ---\n"
                )
        
        # Construir prompt completo para LlamaIndex
        user_prompt = self._get_epc_user_prompt(examples_text).format(
            hce_text=hce_text,
            pages=pages,
        )
        
        # Inyectar contexto RAG entre examples y HCE
        if rag_context_text:
            user_prompt = rag_context_text + "\n" + user_prompt
        
        full_prompt = f"{system_prompt}\n\n---\n\nUSER:\n{user_prompt}"
        
        try:
            # LlamaIndex: llamada directa al LLM
            from llama_index.core.llms import ChatMessage, MessageRole
            
            messages = [
                ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
                ChatMessage(role=MessageRole.USER, content=user_prompt),
            ]
            
            response = await self.llm.achat(messages)
            response_text = response.message.content
            
            # Parsear JSON de respuesta
            result = self._parse_json_response(response_text)
            
            # Tracking de uso
            try:
                from app.services.llm_usage_tracker import get_llm_usage_tracker
                tracker = get_llm_usage_tracker()
                
                # Estimar tokens (aproximación: 1 token ≈ 4 caracteres)
                input_tokens = len(full_prompt) // 4
                output_tokens = len(response_text) // 4
                
                await tracker.track_usage(
                    operation_type="epc_generation",
                    model=self.model_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    metadata={"pages": pages, "has_examples": bool(feedback_examples), "framework": "llamaindex"},
                )
            except Exception as track_err:
                log.warning("[LlamaIndexAI] Failed to track usage: %s", track_err)
            
            # ⚠️ POST-PROCESAMIENTO OBLIGATORIO: Asegurar cumplimiento de reglas
            result = _post_process_epc_result(result)
            log.info("[LlamaIndexAI] Post-procesamiento de reglas aplicado")
            
            if span_ctx:
                span.set_attribute("output_length", len(response_text))
                span.__exit__(None, None, None)
            
            return {
                "json": result,
                "_provider": "llamaindex",
                "_model": self.model_name,
                "_generated_at": datetime.utcnow().isoformat(),
                "_feedback_insights_used": bool(feedback_rules),
                "_post_processed": True,
            }
            
        except Exception as e:
            log.error("[LlamaIndexAI] Error generating EPC: %s", e)
            if span_ctx:
                span.set_attribute("error", str(e))
                span.__exit__(type(e), e, None)
            raise RuntimeError(f"Error generando EPC: {e}") from e
    
    async def extract_patient_data(self, hce_text: str) -> Dict[str, Any]:
        """Extrae datos demográficos del paciente desde HCE."""
        from llama_index.core.llms import ChatMessage, MessageRole
        
        messages = [
            ChatMessage(role=MessageRole.SYSTEM, content=self._get_patient_extraction_prompt()),
            ChatMessage(role=MessageRole.USER, content=f"Texto de HCE:\n\n{hce_text}"),
        ]
        
        response = await self.llm.achat(messages)
        result = self._parse_json_response(response.message.content)
        return result
    
    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """Parsea respuesta JSON del LLM."""
        # Limpiar markdown si existe
        text = response_text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            log.warning("[LlamaIndexAI] Failed to parse JSON, attempting fix: %s", e)
            # Intentar arreglar JSON común
            try:
                # Reemplazar comillas simples por dobles
                fixed = text.replace("'", '"')
                return json.loads(fixed)
            except:
                log.error("[LlamaIndexAI] Could not parse response as JSON")
                return {}
    
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

ENTONCES la sección "evolucion" DEBE tener esta estructura EXACTA:

1. PRIMERO: Describir TODA la evolución clínica durante la internación (incluyendo circunstancias del fallecimiento)
2. AL FINAL: Agregar una SUBSECCIÓN SEPARADA con el siguiente formato EXACTO:

---
**DESENLACE: ÓBITO**
Fecha: DD/MM/YYYY | Hora: HH:MM
---

⚠️ IMPORTANTE: 
- El bloque de ÓBITO debe estar SIEMPRE AL FINAL de la evolución
- Debe estar SEPARADO del resto del texto por líneas en blanco
- SOLO incluir fecha y hora, SIN descripción adicional (la descripción ya está en el texto de evolución)
- NUNCA mezclar el texto de ÓBITO con los párrafos de evolución clínica

================================================================================
🎯 TABLA DE DECISIÓN RÁPIDA - CLASIFICACIÓN DE SECCIONES
================================================================================

⛔ REGLA DE ORO (OBLIGATORIO):
- "mirar/medir" sin invadir → ESTUDIO COMPLEMENTARIO
- "hacer" invasivo/intervencionista → PROCEDIMIENTO  
- "opinar/evaluar" por otra especialidad → INTERCONSULTA
- Análisis de muestras biológicas → LABORATORIO

| Tipo | Ejemplos | Sección |
|------|----------|---------|
| Imágenes | Rx, Eco, TAC, RM, ECG, ETT | Estudios |
| Endoscopías | VEDA, colonoscopía, CPRE | Procedimientos |
| Invasivos | Biopsia, punción, CVC, IOT | Procedimientos |
| Especialistas | "Visto por Cardio/Infecto..." | Interconsultas |
| Análisis | Hemograma, urea, cultivos | Laboratorio |

================================================================================
📋 SECCIÓN: PROCEDIMIENTOS - REGLAS OBLIGATORIAS
================================================================================

⛔ DEFINICIÓN: Solo intervenciones invasivas/intervencionistas REALIZADAS.
INCLUIR: Cirugías, endoscopías (VEDA), cateterismos, biopsias, IOT, CVC, transfusiones, RCP.
EXCLUIR: Rutinas enfermería, controles, estudios de imagen, laboratorios.

FORMATO OBLIGATORIO:
"DD/MM/YYYY HH:MM - [Servicio] Procedimiento. Motivo: X. Hallazgos: Y."

⛔ FORMATO DE FECHA: USAR SIEMPRE DD/MM/YYYY (ejemplo: 10/07/2025)
⛔ NUNCA usar formato YYYY-MM-DD (ejemplo: 2025-07-10) - ESTO ES UN ERROR

⛔ REGLAS CRÍTICAS:
1. Solo procedimientos INVASIVOS/INTERVENCIONISTAS realizados
2. NUNCA escribir procedimiento sin fecha
3. Si usa sigla, aclararla: "VEDA (Videoendoscopía Digestiva Alta)"
4. ORDENAR cronológicamente

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
{"tipo": "internacion" | "previa", "farmaco": "nombre", "dosis": "cantidad", "via": "IV|Oral|SC|IM", "frecuencia": "cada X hs"}

⛔ CLASIFICACIÓN OBLIGATORIA:

"previa" = medicación que el paciente YA TOMABA ANTES de ingresar:
- Buscar en: "antecedentes", "medicación habitual", "tratamiento crónico"

"internacion" = medicación INDICADA DURANTE la hospitalización:
- Buscar en: "indicaciones médicas", "plan terapéutico", "se inicia", "se indica"

================================================================================
📋 SECCIÓN: INDICACIONES AL ALTA - REGLAS OBLIGATORIAS
================================================================================
- Si el paciente FALLECIÓ, esta sección DEBE estar VACÍA []

================================================================================
📋 SECCIÓN: RECOMENDACIONES - REGLAS OBLIGATORIAS
================================================================================

⛔ REGLA FUNDAMENTAL:
- Si el paciente FALLECIÓ, esta sección DEBE estar VACÍA []
- Las recomendaciones deben basarse en la EVOLUCIÓN del paciente durante la internación

✅ REGLAS DE ESTILO MÉDICO:
1. Redactar con ROL MÉDICO y LÉXICO PROFESIONAL
2. Usar terminología médica precisa y formal
3. Las recomendaciones deben ser personalizadas según la evolución clínica del paciente

⛔ ERRORES COMUNES A EVITAR (NO HACER):
- ❌ "Consultar si fiebre mayor a 38°C" → Redundante (fiebre YA es >38°C)
- ❌ "Control si presenta fiebre" → Impreciso
- ✅ CORRECTO: "Control precoz ante temperatura ≥38°C o deterioro del estado general"

- ❌ "Tomar medicación según indicación" → Genérico
- ✅ CORRECTO: "Cumplir tratamiento antibiótico por 7 días según esquema indicado"

- ❌ "Hacer reposo" → Vago
- ✅ CORRECTO: "Reposo relativo con movilización progresiva según tolerancia"

📋 ESTRUCTURA DE RECOMENDACIONES:
1. Controles clínicos específicos (qué monitorear y cuándo)
2. Signos de alarma claros (cuándo consultar urgente)
3. Seguimiento por especialidades según interconsultas realizadas
4. Indicaciones de actividad física/dieta si aplica
5. Controles de estudios pendientes si corresponde

################################################################################
ESTRUCTURA DE RESPUESTA (JSON):
################################################################################
{
  "motivo_internacion": "string",
  "evolucion": "string (⛔ si hay fallecimiento, el último párrafo DEBE comenzar con 'PACIENTE OBITÓ - Fecha: ...')",
  "procedimientos": ["DD/MM/YYYY HH:MM - Descripción"],
  "interconsultas": ["DD/MM/YYYY HH:MM - Especialidad"],
  "medicacion": [
    {"tipo": "internacion|previa", "farmaco": "nombre", "dosis": "cantidad", "via": "IV|Oral|SC|IM", "frecuencia": "cada X hs"}
  ],
  "indicaciones_alta": ["string (VACÍO si paciente falleció)"],
  "recomendaciones": ["string (VACÍO si paciente falleció)"],
  "diagnostico_principal": "string | null",
  "diagnosticos_secundarios": ["string"]
}"""
    
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
{
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
}"""
    
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
# Factory function (compatible con LangChain version)
# ============================================================================

def get_ai_service(use_llamaindex: bool = True) -> Any:
    """
    Factory para obtener el servicio de IA apropiado.
    
    FERRO D2 v4: Por defecto usa LlamaIndex.
    
    Args:
        use_llamaindex: Si True, usa LlamaIndex. Si False, usa servicio legacy.
    
    Returns:
        Instancia del servicio de IA
    """
    if use_llamaindex:
        try:
            return LlamaIndexAIService()
        except Exception as e:
            log.warning("[get_ai_service] LlamaIndex failed, falling back to legacy: %s", e)
    
    # Fallback al servicio legacy
    from app.services.ai_gemini_service import GeminiAIService
    return GeminiAIService()


# Alias para compatibilidad con código que importa LangChainAIService
LangChainAIService = LlamaIndexAIService
