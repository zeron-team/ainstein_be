# backend/app/services/rag_service.py
"""
Servicio RAG (Retrieval Augmented Generation) para EPICRISIS.

Integra:
- LangChain para orquestación de LLM
- Qdrant para recuperación de contexto similar
- Feedback loop para few-shot learning
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from app.core.config import settings
from app.adapters.mongo_client import db as mongo

log = logging.getLogger(__name__)


class RAGService:
    """
    Servicio de RAG para generación mejorada de EPCs.
    
    Flujo:
    1. Recibe HCE text
    2. Recupera chunks similares de otras HCEs (contexto)
    3. Recupera EPCs exitosas como few-shot examples
    4. Genera EPC con contexto enriquecido
    5. Guarda EPC exitosa para futuro few-shot learning
    """
    
    def __init__(self, use_vector_store: bool = True):
        self._use_vector_store = use_vector_store
        self._ai_service = None
        self._vector_service = None
    
    @property
    def ai_service(self):
        """Lazy load del servicio de IA."""
        if self._ai_service is None:
            from app.services.ai_langchain_service import LangChainAIService
            self._ai_service = LangChainAIService()
        return self._ai_service
    
    @property
    def vector_service(self):
        """Lazy load del servicio vectorial."""
        if self._vector_service is None and self._use_vector_store:
            try:
                from app.services.vector_service import get_vector_service
                self._vector_service = get_vector_service()
            except Exception as e:
                log.warning("[RAGService] Vector store not available: %s", e)
                self._vector_service = None
        return self._vector_service
    
    async def generate_epc_with_rag(
        self,
        hce_text: str,
        patient_id: Optional[str] = None,
        pages: int = 0,
    ) -> Dict[str, Any]:
        """
        Genera EPC con RAG - recuperando contexto similar y ejemplos exitosos.
        
        Args:
            hce_text: Texto de la HCE
            patient_id: ID del paciente (opcional, para filtrado)
            pages: Número de páginas
        
        Returns:
            Diccionario con EPC generada y metadatos
        """
        feedback_examples = []
        similar_context = []
        
        # Paso 1: Recuperar feedback exitoso para few-shot learning
        if self.vector_service:
            try:
                # Obtener ejemplos de EPCs con rating OK
                feedback_examples = await self._get_feedback_examples(hce_text)
                log.info("[RAGService] Retrieved %d feedback examples", len(feedback_examples))
            except Exception as e:
                log.warning("[RAGService] Failed to get feedback examples: %s", e)
        
        # Paso 2: Recuperar chunks similares de otras HCEs (si está activo)
        if self.vector_service:
            try:
                similar_context = await self.vector_service.search_similar_hce_chunks(
                    query_text=hce_text[:2000],  # Primeros 2000 chars para query
                    limit=3,
                )
                log.info("[RAGService] Retrieved %d similar HCE chunks", len(similar_context))
            except Exception as e:
                log.warning("[RAGService] Failed to search similar chunks: %s", e)
        
        # Paso 3: Generar EPC con LangChain
        result = await self.ai_service.generate_epc(
            hce_text=hce_text,
            pages=pages,
            feedback_examples=feedback_examples,
        )
        
        # Agregar metadatos de RAG
        result["_rag_enabled"] = self._use_vector_store
        result["_feedback_examples_count"] = len(feedback_examples)
        result["_similar_context_count"] = len(similar_context)
        
        return result
    
    async def _get_feedback_examples(self, hce_text: str) -> List[Dict[str, Any]]:
        """
        Obtiene ejemplos de feedback exitoso para few-shot learning.
        Usa MongoDB epc_feedback para encontrar EPCs con rating "ok".
        """
        examples = []
        
        # Buscar en MongoDB los feedbacks con rating OK más recientes
        cursor = mongo.epc_feedback.find(
            {"rating": "ok", "original_content": {"$ne": None}},
            sort=[("created_at", -1)],
            limit=10,
        )
        
        async for doc in cursor:
            examples.append({
                "section": doc.get("section", ""),
                "original_content": doc.get("original_content", ""),
                "epc_id": doc.get("epc_id", ""),
            })
        
        return examples
    
    async def save_successful_epc(
        self,
        epc_id: str,
        section: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Guarda una EPC exitosa para futuro few-shot learning.
        Llamar cuando un usuario da rating "ok" a una sección.
        """
        if not self.vector_service:
            log.debug("[RAGService] Vector store not available, skipping save")
            return
        
        try:
            await self.vector_service.add_successful_epc(
                epc_id=epc_id,
                section=section,
                content=content,
                metadata=metadata or {},
            )
            log.info("[RAGService] Saved successful EPC for few-shot: %s/%s", epc_id, section)
        except Exception as e:
            log.warning("[RAGService] Failed to save successful EPC: %s", e)


# ============================================================================
# Función de migración gradual
# ============================================================================

async def generate_epc_smart(
    hce_text: str,
    patient_id: Optional[str] = None,
    pages: int = 0,
    use_rag: bool = True,
    fallback_to_legacy: bool = True,
) -> Dict[str, Any]:
    """
    Función de alto nivel para generar EPC.
    Intenta usar RAG primero, con fallback a servicio legacy.
    
    Args:
        hce_text: Texto de la HCE
        patient_id: ID del paciente
        pages: Número de páginas
        use_rag: Si usar RAG (default True)
        fallback_to_legacy: Si hacer fallback al servicio legacy en caso de error
    
    Returns:
        Diccionario con EPC generada
    """
    if use_rag:
        try:
            rag = RAGService(use_vector_store=True)
            return await rag.generate_epc_with_rag(
                hce_text=hce_text,
                patient_id=patient_id,
                pages=pages,
            )
        except Exception as e:
            log.warning("[generate_epc_smart] RAG failed: %s", e)
            if not fallback_to_legacy:
                raise
    
    # Fallback a servicio legacy
    log.info("[generate_epc_smart] Using legacy Gemini service")
    from app.services.ai_gemini_service import GeminiAIService
    
    ai = GeminiAIService()
    # Construir prompt básico
    prompt = _build_legacy_prompt(hce_text, pages)
    return await ai.generate_epc(prompt)


def _build_legacy_prompt(hce_text: str, pages: int) -> str:
    """Construye prompt para servicio legacy."""
    return f"""Genera una Epicrisis profesional basándote en esta HCE ({pages} páginas).
Responde SOLO con JSON válido.

HCE:
{hce_text}

Estructura requerida:
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
