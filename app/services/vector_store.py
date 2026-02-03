# app/services/vector_store.py
"""
Qdrant Vector Store for FERRO Protocol - Semantic Layer (Vector Brain)
Provides embedding and semantic search for personalized RAG.
"""
from typing import Optional, List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.core.config import settings
import logging
import hashlib

log = logging.getLogger(__name__)

# Global Qdrant client
_qdrant_client: Optional[QdrantClient] = None
_embeddings: Optional[GoogleGenerativeAIEmbeddings] = None

# Collection names
FEEDBACK_COLLECTION = "epc_feedback_vectors"
VECTOR_DIM = 768  # Gemini embedding dimension


def get_qdrant_client() -> Optional[QdrantClient]:
    """Get or create Qdrant client."""
    global _qdrant_client
    if not settings.QDRANT_ENABLED:
        return None
    
    if _qdrant_client is None:
        try:
            _qdrant_client = QdrantClient(
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT
            )
            log.info(f"[Qdrant] Connected to {settings.QDRANT_HOST}:{settings.QDRANT_PORT}")
        except Exception as e:
            log.warning(f"[Qdrant] Connection failed: {e}")
            return None
    return _qdrant_client


def get_embeddings() -> Optional[GoogleGenerativeAIEmbeddings]:
    """Get or create Gemini embeddings model."""
    global _embeddings
    if _embeddings is None:
        try:
            _embeddings = GoogleGenerativeAIEmbeddings(
                model="models/embedding-001",
                google_api_key=settings.GEMINI_API_KEY
            )
            log.info("[Qdrant] Embeddings model initialized (Gemini)")
        except Exception as e:
            log.warning(f"[Qdrant] Embeddings init failed: {e}")
            return None
    return _embeddings


async def ensure_collection():
    """Ensure feedback collection exists."""
    client = get_qdrant_client()
    if not client:
        return False
    
    try:
        client.get_collection(FEEDBACK_COLLECTION)
        return True
    except UnexpectedResponse:
        # Create collection
        client.create_collection(
            collection_name=FEEDBACK_COLLECTION,
            vectors_config=models.VectorParams(
                size=VECTOR_DIM,
                distance=models.Distance.COSINE
            )
        )
        log.info(f"[Qdrant] Created collection: {FEEDBACK_COLLECTION}")
        return True
    except Exception as e:
        log.error(f"[Qdrant] Collection check failed: {e}")
        return False


def generate_point_id(user_id: str, section: str, text: str) -> str:
    """Generate deterministic point ID for deduplication."""
    data = f"{user_id}:{section}:{text}"
    return hashlib.md5(data.encode()).hexdigest()


async def store_feedback_vector(
    user_id: str,
    section: str,
    rating: str,
    feedback_text: str,
    has_omissions: bool = False,
    has_repetitions: bool = False,
    is_confusing: bool = False
) -> bool:
    """
    Store feedback as vector in Qdrant.
    Returns True if successful.
    """
    client = get_qdrant_client()
    embeddings = get_embeddings()
    
    if not client or not embeddings:
        return False
    
    if not feedback_text or len(feedback_text.strip()) < 5:
        return False
    
    try:
        # Ensure collection exists
        await ensure_collection()
        
        # Create embedding
        vector = embeddings.embed_query(feedback_text)
        
        # Create payload with metadata
        payload = {
            "user_id": user_id,
            "section": section,
            "rating": rating,
            "text": feedback_text,
            "has_omissions": has_omissions,
            "has_repetitions": has_repetitions,
            "is_confusing": is_confusing,
            "rule_type": "maintain" if rating == "ok" else "avoid"
        }
        
        # Upsert point
        point_id = generate_point_id(user_id, section, feedback_text)
        client.upsert(
            collection_name=FEEDBACK_COLLECTION,
            points=[
                models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload
                )
            ]
        )
        
        log.debug(f"[Qdrant] Stored feedback vector for user={user_id}, section={section}")
        return True
        
    except Exception as e:
        log.error(f"[Qdrant] Failed to store vector: {e}")
        return False


async def search_similar_feedback(
    user_id: str,
    section: str,
    query_text: str,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    Search for similar feedback from this user for this section.
    Returns list of similar feedback with scores.
    """
    client = get_qdrant_client()
    embeddings = get_embeddings()
    
    if not client or not embeddings:
        return []
    
    try:
        # Create query embedding
        query_vector = embeddings.embed_query(query_text)
        
        # Search with filter
        results = client.search(
            collection_name=FEEDBACK_COLLECTION,
            query_vector=query_vector,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="user_id",
                        match=models.MatchValue(value=user_id)
                    ),
                    models.FieldCondition(
                        key="section",
                        match=models.MatchValue(value=section)
                    )
                ]
            ),
            limit=top_k
        )
        
        return [
            {
                "text": hit.payload.get("text"),
                "rating": hit.payload.get("rating"),
                "rule_type": hit.payload.get("rule_type"),
                "score": hit.score
            }
            for hit in results
        ]
        
    except Exception as e:
        log.error(f"[Qdrant] Search failed: {e}")
        return []


async def get_user_rules_from_vectors(
    user_id: str,
    sections: List[str],
    sample_text: str = "reglas de estilo para generación de epicrisis"
) -> Dict[str, List[str]]:
    """
    Get personalized rules per section from vector similarity search.
    Returns dict: {section: [rules]}
    """
    rules = {}
    
    for section in sections:
        similar = await search_similar_feedback(user_id, section, sample_text, top_k=3)
        if similar:
            section_rules = []
            for hit in similar:
                if hit.get("score", 0) > 0.5:  # Only high-confidence matches
                    rule_type = hit.get("rule_type", "avoid")
                    text = hit.get("text", "")
                    if rule_type == "maintain":
                        section_rules.append(f"MANTENER: {text}")
                    else:
                        section_rules.append(f"EVITAR: {text}")
            if section_rules:
                rules[section] = section_rules
    
    return rules


# Health check for Qdrant
async def qdrant_health() -> dict:
    """Check Qdrant health status."""
    if not settings.QDRANT_ENABLED:
        return {"status": "disabled", "message": "Qdrant not enabled"}
    
    client = get_qdrant_client()
    if client:
        try:
            collections = client.get_collections()
            return {
                "status": "ok",
                "message": f"Qdrant connected, {len(collections.collections)} collections",
                "collections": [c.name for c in collections.collections]
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "error", "message": "Qdrant client not available"}
