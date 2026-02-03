# app/services/vector/qdrant_service.py
"""
Servicio unificado de Qdrant.

Consolida funcionalidad de:
- vector_store.py (feedback de usuarios)
- vector_service.py (HCE chunks y RAG)

Principios SOLID:
- S: Solo operaciones de Qdrant
- O: Extensible para nuevas colecciones
- D: Depende de EmbeddingService (abstracción)
"""

from __future__ import annotations

import logging
import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from app.core.config import settings
from .embedding_service import get_embedding_service

log = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Resultado de búsqueda vectorial."""
    id: str
    score: float
    text: str
    metadata: Dict[str, Any]


class QdrantService:
    """
    Servicio unificado para operaciones con Qdrant.
    
    Colecciones:
    - hce_chunks: Chunks de HCEs para RAG
    - epc_feedback: Feedback de usuarios para personalización
    
    Uso:
        service = QdrantService()
        await service.add_hce_chunk(chunk_id, text, metadata)
        results = await service.search_hce_chunks(query, limit=5)
    """
    
    # Nombres de colecciones
    COLLECTION_HCE_CHUNKS = "hce_chunks"
    COLLECTION_EPC_FEEDBACK = "epc_feedback_vectors"
    
    # Configuración
    VECTOR_DIM = 768
    
    def __init__(self):
        self._client = None
        self._initialized = False
        self._embedding_service = get_embedding_service()
    
    def _initialize(self):
        """Inicialización lazy del cliente Qdrant."""
        if self._initialized:
            return
        
        if not getattr(settings, "QDRANT_ENABLED", True):
            log.warning("[QdrantService] Qdrant disabled in settings")
            return
        
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams
            
            host = getattr(settings, "QDRANT_HOST", "localhost")
            port = int(getattr(settings, "QDRANT_PORT", 6333))
            
            self._client = QdrantClient(host=host, port=port)
            self._ensure_collections()
            self._initialized = True
            
            log.info(f"[QdrantService] Connected to {host}:{port}")
            
        except ImportError:
            log.warning("[QdrantService] qdrant-client not installed")
        except Exception as e:
            log.warning(f"[QdrantService] Connection failed: {e}")
    
    def _ensure_collections(self):
        """Crea colecciones si no existen."""
        from qdrant_client.models import Distance, VectorParams
        from qdrant_client.http.exceptions import UnexpectedResponse
        
        collections = [
            self.COLLECTION_HCE_CHUNKS,
            self.COLLECTION_EPC_FEEDBACK,
        ]
        
        for coll_name in collections:
            try:
                self._client.get_collection(coll_name)
            except UnexpectedResponse:
                self._client.create_collection(
                    collection_name=coll_name,
                    vectors_config=VectorParams(
                        size=self.VECTOR_DIM,
                        distance=Distance.COSINE
                    ),
                )
                log.info(f"[QdrantService] Created collection: {coll_name}")
    
    @property
    def client(self):
        """Cliente Qdrant (lazy init)."""
        if not self._initialized:
            self._initialize()
        return self._client
    
    @property
    def is_available(self) -> bool:
        """Verifica si Qdrant está disponible."""
        return self.client is not None
    
    # =========================================================================
    # HCE CHUNKS (para RAG)
    # =========================================================================
    
    async def add_hce_chunk(
        self,
        chunk_id: str,
        text: str,
        metadata: Dict[str, Any],
    ) -> bool:
        """
        Agrega un chunk de HCE para RAG.
        
        Args:
            chunk_id: ID único del chunk
            text: Texto del chunk
            metadata: Metadatos (hce_id, patient_id, tipo, fecha, etc.)
            
        Returns:
            True si se guardó correctamente
        """
        if not self.is_available:
            return False
        
        try:
            from qdrant_client.models import PointStruct
            
            vector = await self._embedding_service.embed(text)
            
            self.client.upsert(
                collection_name=self.COLLECTION_HCE_CHUNKS,
                points=[
                    PointStruct(
                        id=chunk_id,
                        vector=vector,
                        payload={
                            "text": text,
                            "created_at": datetime.utcnow().isoformat(),
                            **metadata,
                        },
                    )
                ],
            )
            return True
            
        except Exception as e:
            log.error(f"[QdrantService] Failed to add HCE chunk: {e}")
            return False
    
    async def search_hce_chunks(
        self,
        query_text: str,
        limit: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """
        Busca chunks de HCE similares.
        
        Args:
            query_text: Texto de búsqueda
            limit: Cantidad máxima de resultados
            filter_dict: Filtros opcionales (hce_id, patient_id, etc.)
            
        Returns:
            Lista de SearchResult ordenados por score
        """
        if not self.is_available:
            return []
        
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            
            vector = await self._embedding_service.embed(query_text)
            
            qdrant_filter = None
            if filter_dict:
                conditions = [
                    FieldCondition(key=k, match=MatchValue(value=v))
                    for k, v in filter_dict.items()
                ]
                qdrant_filter = Filter(must=conditions)
            
            results = self.client.search(
                collection_name=self.COLLECTION_HCE_CHUNKS,
                query_vector=vector,
                limit=limit,
                query_filter=qdrant_filter,
            )
            
            return [
                SearchResult(
                    id=str(r.id),
                    score=r.score,
                    text=r.payload.get("text", ""),
                    metadata={k: v for k, v in r.payload.items() if k != "text"},
                )
                for r in results
            ]
            
        except Exception as e:
            log.error(f"[QdrantService] Search failed: {e}")
            return []
    
    # =========================================================================
    # FEEDBACK (para personalización)
    # =========================================================================
    
    def _generate_feedback_id(self, user_id: str, section: str, text: str) -> str:
        """Genera ID determinístico para deduplicación."""
        data = f"{user_id}:{section}:{text}"
        return hashlib.md5(data.encode()).hexdigest()
    
    async def store_feedback(
        self,
        user_id: str,
        section: str,
        rating: str,
        feedback_text: str,
        has_omissions: bool = False,
        has_repetitions: bool = False,
        is_confusing: bool = False,
    ) -> bool:
        """
        Almacena feedback del usuario como vector.
        
        Args:
            user_id: ID del usuario
            section: Sección de la EPC (evolucion, medicacion, etc.)
            rating: "ok" o "bad"
            feedback_text: Texto del feedback
            
        Returns:
            True si se guardó correctamente
        """
        if not self.is_available:
            return False
        
        if not feedback_text or len(feedback_text.strip()) < 5:
            return False
        
        try:
            from qdrant_client.models import PointStruct
            
            vector = await self._embedding_service.embed(feedback_text)
            point_id = self._generate_feedback_id(user_id, section, feedback_text)
            
            payload = {
                "user_id": user_id,
                "section": section,
                "rating": rating,
                "text": feedback_text,
                "has_omissions": has_omissions,
                "has_repetitions": has_repetitions,
                "is_confusing": is_confusing,
                "rule_type": "maintain" if rating == "ok" else "avoid",
                "created_at": datetime.utcnow().isoformat(),
            }
            
            self.client.upsert(
                collection_name=self.COLLECTION_EPC_FEEDBACK,
                points=[
                    PointStruct(
                        id=point_id,
                        vector=vector,
                        payload=payload,
                    )
                ],
            )
            
            log.debug(f"[QdrantService] Stored feedback for user={user_id}, section={section}")
            return True
            
        except Exception as e:
            log.error(f"[QdrantService] Failed to store feedback: {e}")
            return False
    
    async def search_user_feedback(
        self,
        user_id: str,
        section: str,
        query_text: str,
        limit: int = 5,
    ) -> List[SearchResult]:
        """
        Busca feedback similar de un usuario para una sección.
        
        Args:
            user_id: ID del usuario
            section: Sección de la EPC
            query_text: Texto de búsqueda
            limit: Cantidad máxima de resultados
            
        Returns:
            Lista de resultados ordenados por similitud
        """
        if not self.is_available:
            return []
        
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            
            vector = await self._embedding_service.embed(query_text)
            
            results = self.client.search(
                collection_name=self.COLLECTION_EPC_FEEDBACK,
                query_vector=vector,
                query_filter=Filter(
                    must=[
                        FieldCondition(key="user_id", match=MatchValue(value=user_id)),
                        FieldCondition(key="section", match=MatchValue(value=section)),
                    ]
                ),
                limit=limit,
            )
            
            return [
                SearchResult(
                    id=str(r.id),
                    score=r.score,
                    text=r.payload.get("text", ""),
                    metadata={k: v for k, v in r.payload.items() if k != "text"},
                )
                for r in results
            ]
            
        except Exception as e:
            log.error(f"[QdrantService] Feedback search failed: {e}")
            return []
    
    # =========================================================================
    # HEALTH CHECK
    # =========================================================================
    
    async def health_check(self) -> Dict[str, Any]:
        """Verifica estado de Qdrant."""
        if not getattr(settings, "QDRANT_ENABLED", True):
            return {"status": "disabled", "message": "Qdrant not enabled"}
        
        if not self.is_available:
            return {"status": "error", "message": "Qdrant client not available"}
        
        try:
            collections = self.client.get_collections()
            return {
                "status": "ok",
                "message": f"Connected, {len(collections.collections)} collections",
                "collections": [c.name for c in collections.collections],
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


# Singleton global
_qdrant_service: Optional[QdrantService] = None


def get_qdrant_service() -> QdrantService:
    """Obtiene instancia singleton del servicio Qdrant."""
    global _qdrant_service
    if _qdrant_service is None:
        _qdrant_service = QdrantService()
    return _qdrant_service
