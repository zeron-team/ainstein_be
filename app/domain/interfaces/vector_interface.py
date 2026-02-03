# app/domain/interfaces/vector_interface.py
"""
Interface para servicios de base de datos vectorial.

Principio SOLID: D (Dependency Inversion)
- Permite cambiar Qdrant por Pinecone, Weaviate, etc.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass


@dataclass
class VectorSearchResult:
    """Resultado de búsqueda vectorial."""
    id: str
    score: float
    text: str
    metadata: Dict[str, Any]


class IVectorStore(ABC):
    """
    Interface abstracta para almacenamiento vectorial.
    
    Implementaciones:
    - app.services.vector.qdrant_service.QdrantService
    - Futuro: PineconeService, WeaviateService, etc.
    """
    
    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Indica si el servicio está disponible."""
        pass
    
    @abstractmethod
    async def add_document(
        self,
        collection: str,
        doc_id: str,
        text: str,
        metadata: Dict[str, Any],
    ) -> bool:
        """
        Agrega un documento a una colección.
        
        Args:
            collection: Nombre de la colección
            doc_id: ID único del documento
            text: Texto a vectorizar y almacenar
            metadata: Metadatos asociados
            
        Returns:
            True si se guardó correctamente
        """
        pass
    
    @abstractmethod
    async def search(
        self,
        collection: str,
        query_text: str,
        limit: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        """
        Busca documentos similares.
        
        Args:
            collection: Nombre de la colección
            query_text: Texto de búsqueda
            limit: Cantidad máxima de resultados
            filters: Filtros opcionales
            
        Returns:
            Lista de resultados ordenados por score
        """
        pass
    
    @abstractmethod
    async def delete_document(
        self,
        collection: str,
        doc_id: str,
    ) -> bool:
        """
        Elimina un documento de una colección.
        
        Args:
            collection: Nombre de la colección
            doc_id: ID del documento
            
        Returns:
            True si se eliminó correctamente
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Verifica estado del servicio."""
        pass
