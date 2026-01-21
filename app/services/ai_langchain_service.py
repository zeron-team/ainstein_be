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
        
        Args:
            hce_text: Texto de la HCE
            pages: Número de páginas (para contexto)
            feedback_examples: Ejemplos de EPCs exitosas para few-shot learning
        
        Returns:
            Diccionario con contenido generado y metadatos
        """
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
            
            # Trackear uso de tokens y costo
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
            
            return {
                "json": result,
                "_provider": "langchain",
                "_model": self.model_name,
                "_generated_at": datetime.utcnow().isoformat(),
                "_feedback_insights_used": bool(feedback_rules),
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

REGLAS ESTRICTAS:
1. SOLO usa información presente en el texto de la HCE. NO inventes datos.
2. Si una sección no tiene información, deja el campo vacío o como lista vacía.
3. Usa terminología médica profesional.
4. Sé conciso pero completo.
5. Responde ÚNICAMENTE con JSON válido.

ESTRUCTURA DE RESPUESTA:
{{
  "motivo_internacion": "string",
  "evolucion": "string",
  "procedimientos": ["string"],
  "interconsultas": ["string"],
  "medicacion": ["string"],
  "indicaciones_alta": ["string"],
  "recomendaciones": ["string"],
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
