# app/services/vector/embedding_service.py
"""
Servicio de Embeddings unificado.

Responsabilidad única: Generar embeddings de texto usando Gemini.
"""

from __future__ import annotations

import logging
from typing import List, Optional

log = logging.getLogger(__name__)


class EmbeddingService:
    """
    Servicio para generación de embeddings con Gemini.
    
    Uso:
        service = EmbeddingService()
        vector = await service.embed("texto a vectorizar")
        vectors = await service.embed_batch(["texto1", "texto2"])
    """
    
    # Modelo de embeddings de Gemini
    MODEL = "models/text-embedding-004"
    VECTOR_DIM = 768
    
    def __init__(self):
        self._embeddings = None
        self._initialized = False
    
    def _initialize(self):
        """Inicialización lazy del modelo de embeddings."""
        if self._initialized:
            return
        
        try:
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
            from app.core.config import settings
            
            self._embeddings = GoogleGenerativeAIEmbeddings(
                model=self.MODEL,
                google_api_key=settings.GEMINI_API_KEY,
            )
            self._initialized = True
            log.info(f"[EmbeddingService] Initialized with {self.MODEL}")
            
        except ImportError as e:
            log.error(f"[EmbeddingService] langchain_google_genai not installed: {e}")
            raise RuntimeError("Embedding dependencies not installed")
        except Exception as e:
            log.error(f"[EmbeddingService] Failed to initialize: {e}")
            raise
    
    @property
    def model(self):
        """Obtiene el modelo de embeddings (lazy init)."""
        if not self._initialized:
            self._initialize()
        return self._embeddings
    
    async def embed(self, text: str) -> List[float]:
        """
        Genera embedding para un texto.
        
        Args:
            text: Texto a vectorizar
            
        Returns:
            Lista de floats (vector de 768 dimensiones)
        """
        if not text or not text.strip():
            return [0.0] * self.VECTOR_DIM
        
        return self.model.embed_query(text)
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Genera embeddings para múltiples textos.
        
        Args:
            texts: Lista de textos a vectorizar
            
        Returns:
            Lista de vectores
        """
        if not texts:
            return []
        
        # Filtrar textos vacíos
        valid_texts = [t for t in texts if t and t.strip()]
        if not valid_texts:
            return [[0.0] * self.VECTOR_DIM for _ in texts]
        
        return self.model.embed_documents(valid_texts)


# Singleton global
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Obtiene instancia singleton del servicio de embeddings."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
