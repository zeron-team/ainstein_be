# app/services/rust_engine.py
"""
Python wrapper for FERRO Rust Engine (ferro_engine).
Provides fallback to pure Python if Rust module not available.
"""
from typing import List, Dict, Any, Tuple, Optional
import logging
import re

log = logging.getLogger(__name__)

# Try to import the Rust module
_rust_available = False
try:
    import ferro_engine as _rust
    _rust_available = True
    log.info("[FERRO] Rust engine loaded successfully")
except ImportError:
    log.warning("[FERRO] Rust engine not available, using Python fallback")
    _rust = None


def is_rust_available() -> bool:
    """Check if Rust engine is available."""
    return _rust_available


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """
    Split text into overlapping chunks for embedding.
    Uses Rust if available, otherwise falls back to Python.
    """
    if _rust_available:
        return _rust.chunk_text(text, chunk_size, overlap)
    
    # Python fallback
    if not text:
        return []
    
    sentences = re.split(r'[.\n]', text)
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        
        if len(current_chunk) + len(sentence) + 2 > chunk_size and current_chunk:
            chunks.append(current_chunk)
            overlap_start = max(0, len(current_chunk) - overlap)
            current_chunk = current_chunk[overlap_start:]
        
        if current_chunk:
            current_chunk += ". "
        current_chunk += sentence
    
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks


def tokenize(text: str) -> List[str]:
    """
    Fast tokenization for embeddings.
    Uses Rust if available, otherwise falls back to Python.
    """
    if _rust_available:
        return _rust.tokenize(text)
    
    # Python fallback
    return [w.lower() for w in re.findall(r'\w+', text)]


def count_tokens(text: str) -> int:
    """
    Count approximate tokens in text.
    Uses Rust if available, otherwise falls back to Python.
    """
    if _rust_available:
        return _rust.count_tokens(text)
    
    # Python fallback - rough approximation
    words = len(re.findall(r'\w+', text))
    chars = len(text) // 4
    return (words + chars) // 2


def clean_medical_text(text: str) -> str:
    """
    Clean medical text for processing.
    Uses Rust if available, otherwise falls back to Python.
    """
    if _rust_available:
        return _rust.clean_medical_text(text)
    
    # Python fallback
    text = re.sub(r'<[^>]+>', '', text)  # Remove HTML
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', text)  # Remove control chars
    text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
    return text.strip()


def parallel_chunk_texts(
    texts: List[str], 
    chunk_size: int = 1000, 
    overlap: int = 200
) -> List[Tuple[int, List[str]]]:
    """
    Parallel chunk processing for large documents.
    Uses Rust if available, otherwise falls back to Python.
    """
    if _rust_available:
        return _rust.parallel_chunk_texts(texts, chunk_size, overlap)
    
    # Python fallback (sequential)
    return [(i, chunk_text(text, chunk_size, overlap)) for i, text in enumerate(texts)]


def extract_entities(text: str) -> Dict[str, List[str]]:
    """
    Extract medical entities from text.
    Uses Rust if available, otherwise falls back to Python.
    """
    if _rust_available:
        return _rust.extract_entities(text)
    
    # Python fallback
    entities = {}
    
    # Dates
    entities['dates'] = re.findall(r'\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}', text)
    
    # Times
    entities['times'] = re.findall(r'\d{1,2}:\d{2}(?::\d{2})?', text)
    
    # Measurements
    entities['measurements'] = re.findall(
        r'\d+(?:\.\d+)?\s*(?:mg|ml|g|kg|mm|cm|mmHg|bpm|°C|%|mcg|UI)', 
        text
    )
    
    return entities


# Health check for Rust engine
def rust_engine_health() -> dict:
    """Check Rust engine health status."""
    if _rust_available:
        try:
            # Quick test
            test_result = _rust.chunk_text("Test text for FERRO engine.", 100, 20)
            return {
                "status": "ok",
                "message": f"Rust engine v{_rust.__version__}",
                "test_passed": len(test_result) > 0
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {
        "status": "fallback",
        "message": "Using Python fallback (Rust not compiled)"
    }
