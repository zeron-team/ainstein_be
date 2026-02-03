# app/domain/interfaces/__init__.py
"""
Interfaces de dominio para inversión de dependencias (SOLID - D).

Este módulo define contratos abstractos que los servicios deben implementar.
Permite:
- Desacoplar implementaciones de consumidores
- Facilitar testing con mocks
- Intercambiar implementaciones sin modificar código cliente

Uso:
    from app.domain.interfaces import IEmbeddingService, IVectorStore
    
    class MyService:
        def __init__(self, embeddings: IEmbeddingService, vectors: IVectorStore):
            self.embeddings = embeddings
            self.vectors = vectors
"""

from .embedding_interface import IEmbeddingService
from .vector_interface import IVectorStore
from .hce_interface import IHCEExtractor
from .feedback_interface import IFeedbackService
from .epc_generator_interface import IEPCGenerator

__all__ = [
    "IEmbeddingService",
    "IVectorStore",
    "IHCEExtractor",
    "IFeedbackService",
    "IEPCGenerator",
]
