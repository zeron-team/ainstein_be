# app/services/vector/__init__.py
"""
Módulo unificado de servicios vectoriales (Qdrant).

Este módulo consolida:
- vector_store.py (feedback de usuarios)
- vector_service.py (HCE chunks y RAG)

Principio SOLID aplicado:
- S: Cada clase tiene una responsabilidad clara
- O: Extensible sin modificar (nuevas colecciones)
- D: Inversión de dependencias (interfaz común)
"""

from .qdrant_service import (
    QdrantService,
    get_qdrant_service,
)

from .embedding_service import (
    EmbeddingService,
    get_embedding_service,
)

__all__ = [
    "QdrantService",
    "get_qdrant_service",
    "EmbeddingService", 
    "get_embedding_service",
]
