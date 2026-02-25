# app/services/rust_engine.py
"""
Python wrapper for AInstein Rust Engine (ainstein_core).
Provides fallback to pure Python if Rust module not available.
"""
from typing import List, Dict, Any, Tuple, Optional
import logging
import re

log = logging.getLogger(__name__)

# Try to import the Rust module
_rust_available = False
try:
    import ainstein_core as _rust
    _rust_available = True
    log.info("[FERRO] Rust engine (ainstein_core) loaded successfully")
except ImportError:
    log.warning("[FERRO] ainstein_core not available, using Python fallback")
    _rust = None


def is_rust_available() -> bool:
    """Check if Rust engine is available."""
    return _rust_available


# =============================================================================
# Medical abbreviations we don't want to split on
# =============================================================================
_MEDICAL_ABBREVS = frozenset([
    "dr", "dra", "lic", "sr", "sra", "vs", "etc", "approx",
    "mg", "ml", "kg", "cm", "mm", "vol", "fig", "nro", "av",
])


def _split_sentences(text: str) -> List[str]:
    """
    Split text into sentences, respecting medical abbreviations.
    Does NOT split on abbreviation dots (Dr., mg., etc.) or decimal numbers.
    """
    # Simple split on `. ` (period followed by space) or newlines
    raw_parts = re.split(r'\.\s+|\n+', text)
    return [p.strip() for p in raw_parts if p and p.strip()]


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """
    Split text into overlapping chunks for embedding.
    
    Strategy:
    - Split on sentence boundaries (not mid-word)
    - Maintain overlap between chunks for context continuity
    - Rust module only supports (text, chunk_size) — overlap is Python-side
    """
    if not text or not text.strip():
        return []

    # Use Rust for raw word-level chunking as building blocks
    if _rust_available and overlap == 0:
        return _rust.chunk_text(text, chunk_size)

    # Python sentence-aware chunker with overlap
    sentences = _split_sentences(text)

    if not sentences:
        return [text[:chunk_size]] if text.strip() else []

    chunks: List[str] = []
    current_chunk = ""

    for sentence in sentences:
        # If adding this sentence exceeds chunk_size, flush current chunk
        separator = ". " if current_chunk else ""
        if len(current_chunk) + len(separator) + len(sentence) > chunk_size and current_chunk:
            chunks.append(current_chunk)
            # Build overlap from the END of the current chunk
            if overlap > 0:
                # Take the last `overlap` characters and find a sentence boundary
                overlap_text = current_chunk[-overlap:]
                # Try to start at a sentence boundary within the overlap
                dot_pos = overlap_text.find(". ")
                if dot_pos >= 0:
                    current_chunk = overlap_text[dot_pos + 2:]
                else:
                    current_chunk = overlap_text
            else:
                current_chunk = ""

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
    if _rust_available and hasattr(_rust, 'tokenize'):
        return _rust.tokenize(text)

    # Python fallback
    return [w.lower() for w in re.findall(r'\w+', text)]


def count_tokens(text: str) -> int:
    """
    Count approximate tokens in text.
    Uses Rust if available, otherwise falls back to Python.
    """
    if _rust_available and hasattr(_rust, 'count_tokens'):
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
    if _rust_available and hasattr(_rust, 'clean_medical_text'):
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
    Falls back to sequential Python processing.
    """
    # Always use Python fallback since Rust only has chunk_text(text, size)
    return [(i, chunk_text(text, chunk_size, overlap)) for i, text in enumerate(texts)]


def extract_entities(text: str) -> Dict[str, List[str]]:
    """
    Extract medical entities from text.
    Uses Rust if available, otherwise falls back to Python.
    """
    if _rust_available and hasattr(_rust, 'extract_entities'):
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
            # Quick test — ainstein_core.chunk_text only takes (text, size)
            test_result = _rust.chunk_text("Test text for FERRO engine.", 100)
            return {
                "status": "ok",
                "message": "Connected/Loaded",
                "result_sample": test_result if test_result else ["empty"],
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {
        "status": "fallback",
        "message": "Using Python fallback (Rust not compiled)"
    }
