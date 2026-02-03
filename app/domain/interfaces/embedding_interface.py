# app/domain/interfaces/embedding_interface.py
"""
Interface para servicios de embeddings.

Principio SOLID: D (Dependency Inversion)
- Los servicios de alto nivel dependen de esta abstracción
- Permite intercambiar Gemini por OpenAI, local, etc.
"""

from abc import ABC, abstractmethod
from typing import List


class IEmbeddingService(ABC):
    """
    Interface abstracta para generación de embeddings.
    
    Implementaciones:
    - app.services.vector.embedding_service.EmbeddingService (Gemini)
    - Futuro: OpenAIEmbeddingService, LocalEmbeddingService
    """
    
    @property
    @abstractmethod
    def vector_dimension(self) -> int:
        """Dimensión de los vectores generados."""
        pass
    
    @abstractmethod
    async def embed(self, text: str) -> List[float]:
        """
        Genera embedding para un texto.
        
        Args:
            text: Texto a vectorizar
            
        Returns:
            Vector de floats
        """
        pass
    
    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Genera embeddings para múltiples textos.
        
        Args:
            texts: Lista de textos
            
        Returns:
            Lista de vectores
        """
        pass
