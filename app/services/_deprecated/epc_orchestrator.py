"""
EPC Orchestrator - Orquestación con LlamaIndex para generación de EPCs (FERRO D2 v4)

Este módulo coordina toda la generación de EPCs:
1. Parsea HCE desde JSON de Ainstein
2. Crea chunks para embeddings (opcional RAG)
3. Genera cada sección con su propio prompt
4. Aplica post-procesamiento (reglas clínicas)
5. Retorna EPC completa

Arquitectura:
- LlamaIndex para orquestación (migrado desde LangChain)
- Gemini 2.0 Flash como LLM
- Prompts específicos por sección
- Post-procesamiento con reglas fijas
"""

from __future__ import annotations
import logging
import json
from typing import Dict, List, Any, Optional
from datetime import datetime

# FERRO D2 v4: LlamaIndex (migrado desde LangChain)
from llama_index.llms.gemini import Gemini

from app.core.config import settings
from app.services.hce_ainstein_parser import HCEAinsteinParser, ParsedHCE
from app.services.epc_prompts import PROMPT_DIAGNOSTICO_CIE10
from app.services.epc_prompts_v2 import (
    PROMPT_MOTIVO_REAL,
    PROMPT_EVOLUCION_ESTANDAR,
    PROMPT_EVOLUCION_OBITO,
    PROMPT_PROCEDIMIENTOS,
    PROMPT_INTERCONSULTAS,
    PROMPT_PLAN_TERAPEUTICO
)

log = logging.getLogger(__name__)


class EPCOrchestrator:
    """
    Orquestador principal para generación de EPCs con LlamaIndex (FERRO D2 v4).
    
    Coordina:
    - Parsing de HCE
    - Generación por secciones
    - Post-procesamiento
    - Persistencia
    """
    
    def __init__(self, gemini_api_key: Optional[str] = None):
        """
        Inicializa el orquestador.
        
        Args:
            gemini_api_key: API key de Gemini (opcional, usa settings si no se provee)
        """
        api_key = gemini_api_key or settings.GEMINI_API_KEY
        # Usar gemini-2.0-flash como default (más estable que modelos preview)
        model_name = getattr(settings, 'GEMINI_MODEL', 'gemini-2.0-flash')
        # Si el modelo configurado falla, usar flash como fallback
        if 'preview' in model_name.lower() or 'exp' in model_name.lower():
            model_name = 'gemini-2.0-flash'
        
        # FERRO D2 v4: Configurar LLM con LlamaIndex Gemini
        self.llm = Gemini(
            model=f"models/{model_name}",
            api_key=api_key,
            temperature=0.1,  # Bajo para consistencia clínica
        )
        
        # Parser de HCE
        self.parser = HCEAinsteinParser()
        
        log.info("[EPCOrchestrator] Initialized with Gemini 2.0 Flash (LlamaIndex)")
    
    async def _run_chain(self, prompt, **kwargs) -> str:
        """
        Ejecuta una llamada al LLM con LlamaIndex (FERRO D2 v4).
        Migrado desde LCEL de LangChain.
        
        Args:
            prompt: PromptTemplate a usar (LangChain format se convierte a string)
            **kwargs: Variables para el prompt
            
        Returns:
            String de respuesta del LLM
        """
        # Formatear el prompt con los kwargs
        formatted_prompt = prompt.format(**kwargs)
        
        # LlamaIndex API: acomplete en lugar de chain
        response = await self.llm.acomplete(formatted_prompt)
        return response.text
    
    async def generate_epc(
        self,
        hce_json: Dict[str, Any],
        patient_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Genera una EPC completa desde el JSON de HCE.
        
        Args:
            hce_json: JSON completo de HCE desde Ainstein
            patient_id: ID del paciente (opcional)
            
        Returns:
            Dict con la EPC generada
        """
        log.info("[EPCOrchestrator] Starting EPC generation")
        
        # 1. Parsear HCE
        parsed_hce = self.parser.parse_from_ainstein(hce_json)
        log.info(f"[EPCOrchestrator] Parsed HCE {parsed_hce.hce_id}: "
                f"{len(parsed_hce.historia)} entries, {parsed_hce.dias_estada} days")
        
        # 1.5 ⚠️ VALIDACIÓN PRE-GENERACIÓN (Nuevo)
        try:
            from app.services.epc_pre_validator import validate_hce_for_epc
            validation = validate_hce_for_epc(parsed_hce)
            
            if validation.warnings:
                for w in validation.warnings:
                    log.warning(f"[EPCOrchestrator] Pre-validation: {w}")
            
            if validation.is_obito:
                log.info(f"[EPCOrchestrator] ÓBITO DETECTADO - tipo_alta: {validation.tipo_alta_oficial}")
            
            # Guardar contexto de validación para usar en generación
            self._validation = validation
        except Exception as e:
            log.error(f"[EPCOrchestrator] Error en pre-validación: {e}")
            self._validation = None
        
        # 2. Generar cada sección independientemente
        try:
            motivo = await self._generate_motivo(parsed_hce)
            log.info("[EPCOrchestrator] Generated motivo_internacion")
        except Exception as e:
            log.error(f"[EPCOrchestrator] Error generating motivo: {e}")
            motivo = ""
        
        try:
            evolucion = await self._generate_evolucion(parsed_hce)
            log.info("[EPCOrchestrator] Generated evolucion")
        except Exception as e:
            log.error(f"[EPCOrchestrator] Error generating evolucion: {e}")
            evolucion = ""
        
        try:
            procedimientos = await self._generate_procedimientos(parsed_hce)
            log.info(f"[EPCOrchestrator] Generated {len(procedimientos)} procedimientos")
        except Exception as e:
            log.error(f"[EPCOrchestrator] Error generating procedimientos: {e}")
            procedimientos = []
        
        try:
            interconsultas = await self._generate_interconsultas(parsed_hce)
            log.info(f"[EPCOrchestrator] Generated {len(interconsultas)} interconsultas")
        except Exception as e:
            log.error(f"[EPCOrchestrator] Error generating interconsultas: {e}")
            interconsultas = []
        
        try:
            plan_terapeutico = await self._generate_plan_terapeutico(parsed_hce)
            log.info(f"[EPCOrchestrator] Generated plan terapéutico: "
                    f"{len(plan_terapeutico.get('medicacion_internacion', []))} meds internación, "
                    f"{len(plan_terapeutico.get('medicacion_previa', []))} meds previas")
        except Exception as e:
            log.error(f"[EPCOrchestrator] Error generating plan terapeutico: {e}")
            plan_terapeutico = {"medicacion_internacion": [], "medicacion_previa": []}
        
        try:
            diagnostico_cie10 = await self._generate_diagnostico_cie10(parsed_hce)
            log.info(f"[EPCOrchestrator] Generated diagnostico: {diagnostico_cie10[:50] if diagnostico_cie10 else 'N/A'}")
        except Exception as e:
            log.error(f"[EPCOrchestrator] Error generating diagnostico: {e}")
            diagnostico_cie10 = ""
        
        # 3. Construir resultado
        result = {
            "motivo_internacion": motivo,
            "diagnostico_principal_cie10": diagnostico_cie10,
            "evolucion": evolucion,
            "procedimientos": procedimientos,
            "interconsultas": interconsultas,
            "medicacion_internacion": plan_terapeutico.get("medicacion_internacion", []),
            "medicacion_previa": plan_terapeutico.get("medicacion_previa", []),
            "medicacion": (
                plan_terapeutico.get("medicacion_internacion", []) +
                plan_terapeutico.get("medicacion_previa", [])
            ),  # Compatibilidad con código antiguo
            "laboratorios_detalle": parsed_hce.sections.laboratorios,  # NUEVO: Para click-to-expand
            "indicaciones_alta": [],
            "recomendaciones": [],
            "_generated_by": "epc_orchestrator_v2.1_full_features",
            "_generated_at": datetime.now().isoformat(),
            "_hce_id": parsed_hce.hce_id,
            "_patient_id": patient_id or parsed_hce.patient_id,
        }
        
        # 4. ⚠️ POST-PROCESAMIENTO CRÍTICO: Aplicar reglas clínicas
        from app.services.ai_langchain_service import _post_process_epc_result
        result = _post_process_epc_result(result)
        log.info("[EPCOrchestrator] Applied post-processing rules (including death rule)")
        
        log.info("[EPCOrchestrator] EPC generation completed successfully")
        
        return result
    
    async def _generate_motivo(self, parsed_hce: ParsedHCE) -> str:
        """Genera la sección Motivo de Internación (REAL)."""
        # Priorizar motivo extraído de Triage/Admisión
        motivo_text = parsed_hce.sections.motivo_real
        
        # Fallback a texto de ingreso general si no hay específico
        if not motivo_text:
            motivo_text = parsed_hce.sections.ingreso or "No se registró texto de ingreso"
        
        # REGLA EXPLÍCITA: No truncar - recorrer 100% de la HCE
        result = await self._run_chain(
            PROMPT_MOTIVO_REAL,
            motivo_text=motivo_text
        )
        
        return self._extract_from_json_response(result, "motivo_internacion")
    
    async def _generate_evolucion(self, parsed_hce: ParsedHCE) -> str:
        """Genera la sección Evolución (100% Lectura + Reglas V2)."""
        
        # 1. Preparar HISTORIA COMPLETA (lectura 100%)
        # Usamos sections.evoluciones_todas que ya tiene el join cronológico de todo
        historia_completa = "\n".join(parsed_hce.sections.evoluciones_todas)
        
        if not historia_completa:
            historia_completa = "No hay registros en la historia clínica."
        
        # ========================================================================
        # REGLA EXPLÍCITA: RECORRER 100% DE LA HCE SIN TRUNCAR
        # Gemini 2.0 Flash tiene 1M tokens (~4M caracteres)
        # Una HCE típica tiene 50K-200K caracteres, muy por debajo del límite
        # ========================================================================
        log.info(f"[EPCOrchestrator] Historia completa: {len(historia_completa)} caracteres (sin truncar)")
        if len(historia_completa) > 500000:
            log.warning(f"[EPCOrchestrator] Historia muy extensa: {len(historia_completa)} chars. Considerar optimización.")
            
        # 2. Determinar si es ÓBITO
        is_obito = hasattr(self, '_validation') and self._validation and self._validation.is_obito
        
        # 3. Datos demográficos
        fecha_egreso = parsed_hce.fecha_egreso.strftime("%d/%m/%Y") if parsed_hce.fecha_egreso else "No registrada"
        hora_egreso = parsed_hce.fecha_egreso.strftime("%H:%M") if parsed_hce.fecha_egreso else "hora no registrada"
        
        # 4. Seleccionar PROMPT V2
        if is_obito:
            log.info(f"[EPCOrchestrator] Usando PROMPT V2 ESPECIALIZADO PARA ÓBITO")
            prompt_to_use = PROMPT_EVOLUCION_OBITO
            kwargs = {
                "historia_completa": historia_completa,
                "edad": parsed_hce.edad,
                "sexo": parsed_hce.sexo,
                "dias_estada": parsed_hce.dias_estada,
                "fecha_egreso": fecha_egreso,
                "hora_egreso": hora_egreso
            }
        else:
            log.info(f"[EPCOrchestrator] Usando PROMPT V2 ESTÁNDAR (Alta/Derivación)")
            prompt_to_use = PROMPT_EVOLUCION_ESTANDAR
            kwargs = {
                "historia_completa": historia_completa,
                "edad": parsed_hce.edad,
                "sexo": parsed_hce.sexo,
                "dias_estada": parsed_hce.dias_estada,
                "fecha_egreso": fecha_egreso
            }

        # Ejecutar chain
        result = await self._run_chain(prompt_to_use, **kwargs)
        
        return self._extract_from_json_response(result, "evolucion")
    
    async def _generate_procedimientos(self, parsed_hce: ParsedHCE) -> List[str]:
        """Genera lista de procedimientos (Filtrado V2 + Lab Grouping)."""
        raw_procs = [f"[{p.get('fecha')}] {p.get('descripcion')}" for p in parsed_hce.sections.procedimientos]
        
        procs_llm = []
        if raw_procs:
            result = await self._run_chain(
                PROMPT_PROCEDIMIENTOS, 
                procedimientos_list="\n".join(raw_procs)
            )
            procs_llm = self._extract_from_json_response(result, "procedimientos") or []
        
        # Agregar LABORATORIOS AGRUPADOS (Lógica V2)
        if parsed_hce.sections.laboratorios:
            count = len(parsed_hce.sections.laboratorios)
            labs_summary = f"Laboratorios realizados ({count} estudios)"
            procs_llm.append(labs_summary)
            # NOTA: El detalle completo se inyectará en el JSON final en el campo 'laboratorios_detalle'
            
        return procs_llm
    
    async def _generate_interconsultas(self, parsed_hce: ParsedHCE) -> List[str]:
        """Genera resumen de interconsultas (V2)."""
        raw_inter = [f"[{ic.get('fecha')}] {ic.get('contenido')}" for ic in parsed_hce.sections.interconsultas]
        
        if not raw_inter:
            return []
            
        result = await self._run_chain(
            PROMPT_INTERCONSULTAS, 
            interconsultas_text="\n".join(raw_inter)
        )
        return self._extract_from_json_response(result, "interconsultas") or []
    
    async def _generate_plan_terapeutico(self, parsed_hce: ParsedHCE) -> Dict[str, Any]:
        """Genera el plan terapéutico dividido (Internación vs Previa)."""
        
        # Indicaciones durante internación (Formateado limpio)
        indicaciones_parts = []
        for ind in parsed_hce.sections.indicaciones_farmacologicas:
            fecha = ind.get("fecha", "")
            # El objeto 'farmaco' puede venir anidado o plano según el parser
            data_farm = ind.get("farmaco") or {}
            
            # Extraer campos clave
            nombre = data_farm.get("geneDescripcion") or data_farm.get("infaNombreGenerico") or "Fármaco"
            dosis = data_farm.get("enmeDosis") or data_farm.get("infaDosis") or ""
            via = data_farm.get("meviDescripcion") or data_farm.get("infaVia") or ""
            frec = data_farm.get("mefrDescripcion") or ""
            
            indicaciones_parts.append(f"[{fecha}] {nombre} {dosis} {via} {frec}")
            
        # Contexto de ingreso para antecedentes farmacológicos
        antecedentes = parsed_hce.sections.ingreso or ""
        
        result = await self._run_chain(
            PROMPT_PLAN_TERAPEUTICO,
            indicaciones_text="\n".join(indicaciones_parts),
            antecedentes_text=antecedentes  # Sin truncar - 100% HCE
        )
        
        data = self._extract_from_json_response(result, None)  # Extraer root JSON
        
        if not data:
            return {"medicacion_internacion": [], "medicacion_previa": []}
            
        return data
    
    async def _generate_diagnostico_cie10(self, parsed_hce: ParsedHCE) -> str:
        """Genera/extrae el diagnóstico principal con CIE-10."""
        diagnosticos_text = "\n".join(parsed_hce.sections.diagnosticos) if parsed_hce.sections.diagnosticos else "No hay diagnósticos registrados"
        
        result = await self._run_chain(PROMPT_DIAGNOSTICO_CIE10, diagnosticos_text=diagnosticos_text)
        
        return self._extract_from_json_response(result, "diagnostico_principal_cie10")
    
    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """
        Parsea respuesta JSON del LLM.
        
        Args:
            response: String de respuesta del LLM
            
        Returns:
            Dict parseado
        """
        try:
            # Limpiar markdown si existe
            cleaned = response.strip()
            if "```json" in cleaned:
                cleaned = cleaned.split("```json")[1].split("```")[0]
            elif "```" in cleaned:
                cleaned = cleaned.split("```")[1].split("```")[0]
            
            return json.loads(cleaned.strip())
        except json.JSONDecodeError as e:
            log.error(f"[EPCOrchestrator] Error parsing JSON: {e}\nResponse: {response[:200]}")
            return {}
    
    def _extract_from_json_response(self, response: str, key: str) -> Any:
        """
        Extrae un campo específico del JSON de respuesta.
        
        Args:
            response: String de respuesta del LLM
            key: Clave a extraer
            
        Returns:
            Valor del campo o valor por defecto
        """
        parsed = self._parse_json_response(response)
        
        if key is None:
            return parsed
            
        return parsed.get(key, "" if key != "procedimientos" and key != "interconsultas" else [])
