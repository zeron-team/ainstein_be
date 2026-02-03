# app/domain/interfaces/epc_generator_interface.py
"""
Interface para generadores de EPC.

Principio SOLID: D (Dependency Inversion)
- Permite diferentes implementaciones de generación (Gemini, GPT, local)
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass


@dataclass
class EPCSection:
    """Sección generada de EPC."""
    name: str
    content: Any  # str o List[Dict] según sección
    confidence: float = 1.0
    source_chunks: Optional[List[str]] = None


@dataclass
class GeneratedEPC:
    """EPC completa generada."""
    motivo_internacion: str
    evolucion: str
    procedimientos: List[Any]
    interconsultas: List[Any]
    medicacion_internacion: List[Dict]
    medicacion_previa: List[Dict]
    indicaciones_alta: List[str]
    recomendaciones: List[str]
    
    # Metadatos
    model_used: str = ""
    generation_time_ms: int = 0
    tokens_used: int = 0


class IEPCGenerator(ABC):
    """
    Interface abstracta para generación de EPC.
    
    Implementaciones:
    - app.services.ai_gemini_service.GeminiAIService
    - app.services.ai_langchain_service (orquestador)
    - Futuro: GPTEPCGenerator, LocalEPCGenerator
    """
    
    @abstractmethod
    async def generate_section(
        self,
        section_name: str,
        hce_text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> EPCSection:
        """
        Genera una sección específica de EPC.
        
        Args:
            section_name: Nombre de la sección
            hce_text: Texto de HCE fuente
            context: Contexto adicional (paciente, reglas, etc.)
            
        Returns:
            EPCSection con contenido generado
        """
        pass
    
    @abstractmethod
    async def generate_full_epc(
        self,
        hce_text: str,
        patient_context: Optional[Dict[str, Any]] = None,
        user_rules: Optional[Dict[str, List[str]]] = None,
    ) -> GeneratedEPC:
        """
        Genera EPC completa.
        
        Args:
            hce_text: Texto de HCE fuente
            patient_context: Datos del paciente
            user_rules: Reglas de personalización del usuario
            
        Returns:
            GeneratedEPC con todas las secciones
        """
        pass
    
    @abstractmethod
    async def post_process(
        self,
        epc: GeneratedEPC,
        hce_text: str,
    ) -> GeneratedEPC:
        """
        Aplica post-procesamiento (reglas, validaciones).
        
        Args:
            epc: EPC generada
            hce_text: Texto original para validación
            
        Returns:
            EPC procesada con reglas aplicadas
        """
        pass
