# backend/app/services/vector_service.py
"""
Servicio de base de datos vectorial con Qdrant.
Usado para RAG: recuperar HCEs y EPCs similares.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from app.core.config import settings

log = logging.getLogger(__name__)


class VectorService:
    """
    Servicio para operaciones con base de datos vectorial (Qdrant).
    
    Colecciones:
    - hce_chunks: Chunks de HCEs para contexto en generación
    - epc_feedback: EPCs con feedback positivo para few-shot learning
    """
    
    COLLECTION_HCE_CHUNKS = "hce_chunks"
    COLLECTION_EPC_FEEDBACK = "epc_feedback"
    
    def __init__(self):
        self._client = None
        self._embeddings = None
        self._initialized = False
    
    def _initialize(self):
        """Inicialización lazy."""
        if self._initialized:
            return
        
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams
            
            # Configuración de Qdrant
            qdrant_host = getattr(settings, "QDRANT_HOST", "localhost")
            qdrant_port = int(getattr(settings, "QDRANT_PORT", 6333))
            
            self._client = QdrantClient(host=qdrant_host, port=qdrant_port)
            
            # Inicializar embeddings
            self._init_embeddings()
            
            # Crear colecciones si no existen
            self._ensure_collections()
            
            self._initialized = True
            log.info("[VectorService] Initialized with Qdrant at %s:%d", qdrant_host, qdrant_port)
            
        except ImportError:
            log.warning("[VectorService] qdrant-client not installed")
            raise RuntimeError("Qdrant dependencies not installed")
        except Exception as e:
            log.warning("[VectorService] Failed to connect to Qdrant: %s", e)
            raise
    
    def _init_embeddings(self):
        """Inicializa el modelo de embeddings."""
        try:
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
            
            self._embeddings = GoogleGenerativeAIEmbeddings(
                model="models/text-embedding-004",
                google_api_key=settings.GEMINI_API_KEY,
            )
            log.info("[VectorService] Embeddings initialized with text-embedding-004")
        except Exception as e:
            log.warning("[VectorService] Failed to init embeddings: %s", e)
            raise
    
    def _ensure_collections(self):
        """Crea colecciones si no existen."""
        from qdrant_client.models import Distance, VectorParams
        
        collections = self._client.get_collections().collections
        collection_names = [c.name for c in collections]
        
        # Dimensión de embeddings de Gemini text-embedding-004
        vector_size = 768
        
        for coll_name in [self.COLLECTION_HCE_CHUNKS, self.COLLECTION_EPC_FEEDBACK]:
            if coll_name not in collection_names:
                self._client.create_collection(
                    collection_name=coll_name,
                    vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
                )
                log.info("[VectorService] Created collection: %s", coll_name)
    
    @property
    def client(self):
        if not self._initialized:
            self._initialize()
        return self._client
    
    @property
    def embeddings(self):
        if not self._initialized:
            self._initialize()
        return self._embeddings
    
    async def embed_text(self, text: str) -> List[float]:
        """Genera embedding para un texto."""
        return self.embeddings.embed_query(text)
    
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Genera embeddings para múltiples textos."""
        return self.embeddings.embed_documents(texts)
    
    async def add_hce_chunk(
        self,
        chunk_id: str,
        text: str,
        metadata: Dict[str, Any],
    ):
        """Agrega un chunk de HCE a la colección."""
        from qdrant_client.models import PointStruct
        
        vector = await self.embed_text(text)
        
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
    
    async def search_similar_hce_chunks(
        self,
        query_text: str,
        limit: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Busca chunks de HCE similares."""
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        
        vector = await self.embed_text(query_text)
        
        # Construir filtro si se especifica
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
            {
                "id": str(r.id),
                "score": r.score,
                "text": r.payload.get("text", ""),
                "metadata": {k: v for k, v in r.payload.items() if k != "text"},
            }
            for r in results
        ]
    
    async def add_successful_epc(
        self,
        epc_id: str,
        section: str,
        content: str,
        metadata: Dict[str, Any],
    ):
        """Agrega una EPC exitosa (rating OK) para few-shot learning."""
        from qdrant_client.models import PointStruct
        
        vector = await self.embed_text(content)
        point_id = f"{epc_id}_{section}"
        
        self.client.upsert(
            collection_name=self.COLLECTION_EPC_FEEDBACK,
            points=[
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "epc_id": epc_id,
                        "section": section,
                        "content": content,
                        "rating": "ok",
                        "created_at": datetime.utcnow().isoformat(),
                        **metadata,
                    },
                )
            ],
        )
    
    async def get_successful_examples(
        self,
        section: str,
        query_text: str,
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Obtiene ejemplos de EPCs exitosas para few-shot learning.
        Busca ejemplos similares con rating OK.
        """
        return await self.search_similar_hce_chunks(
            query_text=query_text,
            limit=limit,
            filter_dict={"section": section, "rating": "ok"},
        )


# Singleton para uso global
_vector_service: Optional[VectorService] = None


def get_vector_service() -> VectorService:
    """Obtiene instancia singleton del servicio vectorial."""
    global _vector_service
    if _vector_service is None:
        _vector_service = VectorService()
    return _vector_service
