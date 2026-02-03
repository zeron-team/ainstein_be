//! FERRO Protocol - Rust Engine for CPU-bound text processing (v3.0.0)
//! 
//! This module provides high-performance text processing functions
//! that are exposed to Python via PyO3.
//!
//! FERRO D2 v3.0.0 Compliant:
//! - Zero panic: All functions return PyResult
//! - Zero-copy: Uses &str references where possible
//! - Parallel: Rayon for multi-core processing
//!
//! Functions:
//! - chunk_text: Split text into chunks with overlap
//! - tokenize: Fast tokenization for embeddings
//! - count_tokens: Count approximate tokens in text
//! - clean_medical_text: Sanitize medical text for processing
//! - parallel_chunk_texts: Batch process multiple texts
//! - extract_entities: Extract dates, times, measurements

use pyo3::prelude::*;
use pyo3::exceptions::PyValueError;
use rayon::prelude::*;
use regex::Regex;
use unicode_segmentation::UnicodeSegmentation;
use once_cell::sync::Lazy;

// Pre-compiled regex patterns (compiled once, never panic)
static HTML_RE: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"<[^>]+>").expect("Invalid HTML regex - this is a bug")
});

static CONTROL_RE: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"[\x00-\x08\x0B\x0C\x0E-\x1F]").expect("Invalid control char regex - this is a bug")
});

static WHITESPACE_RE: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"\s+").expect("Invalid whitespace regex - this is a bug")
});

static DATE_RE: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}").expect("Invalid date regex - this is a bug")
});

static TIME_RE: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"\d{1,2}:\d{2}(?::\d{2})?").expect("Invalid time regex - this is a bug")
});

static MEASURE_RE: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"\d+(?:\.\d+)?\s*(?:mg|ml|g|kg|mm|cm|mmHg|bpm|°C|%|mcg|UI)")
        .expect("Invalid measurement regex - this is a bug")
});


/// Chunk text into overlapping segments for embedding
/// 
/// Args:
///     text: The input text to chunk
///     chunk_size: Maximum characters per chunk (default: 1000)
///     overlap: Characters to overlap between chunks (default: 200)
/// 
/// Returns:
///     List of text chunks
/// 
/// Raises:
///     ValueError: If chunk_size is 0 or overlap >= chunk_size
#[pyfunction]
#[pyo3(signature = (text, chunk_size=1000, overlap=200))]
fn chunk_text(text: &str, chunk_size: usize, overlap: usize) -> PyResult<Vec<String>> {
    // Validate parameters
    if chunk_size == 0 {
        return Err(PyValueError::new_err("chunk_size must be greater than 0"));
    }
    if overlap >= chunk_size {
        return Err(PyValueError::new_err("overlap must be less than chunk_size"));
    }
    
    if text.is_empty() {
        return Ok(vec![]);
    }
    
    let sentences: Vec<&str> = text.split(|c| c == '.' || c == '\n').collect();
    let mut chunks: Vec<String> = Vec::new();
    let mut current_chunk = String::new();
    
    for sentence in sentences {
        let sentence = sentence.trim();
        if sentence.is_empty() {
            continue;
        }
        
        // Check if adding this sentence exceeds chunk size
        if current_chunk.len() + sentence.len() + 2 > chunk_size && !current_chunk.is_empty() {
            chunks.push(current_chunk.clone());
            
            // Create overlap from end of current chunk
            let overlap_start = if current_chunk.len() > overlap {
                current_chunk.len() - overlap
            } else {
                0
            };
            current_chunk = current_chunk[overlap_start..].to_string();
        }
        
        if !current_chunk.is_empty() {
            current_chunk.push_str(". ");
        }
        current_chunk.push_str(sentence);
    }
    
    // Don't forget the last chunk
    if !current_chunk.is_empty() {
        chunks.push(current_chunk);
    }
    
    Ok(chunks)
}


/// Fast tokenization for embeddings (whitespace + punctuation split)
/// 
/// Args:
///     text: The input text to tokenize
/// 
/// Returns:
///     List of tokens (lowercase)
#[pyfunction]
fn tokenize(text: &str) -> PyResult<Vec<String>> {
    Ok(text.unicode_words()
        .map(|w| w.to_lowercase())
        .collect())
}


/// Count approximate tokens in text (for context length estimation)
/// 
/// Args:
///     text: The input text
/// 
/// Returns:
///     Approximate token count
#[pyfunction]
fn count_tokens(text: &str) -> PyResult<usize> {
    // Rough approximation: ~4 characters per token for Spanish medical text
    let word_count = text.unicode_words().count();
    let char_factor = text.len() / 4;
    
    // Average of word count and character-based estimate
    Ok((word_count + char_factor) / 2)
}


/// Clean medical text for processing
/// 
/// Removes:
/// - Extra whitespace
/// - Special characters (preserving medical notation)
/// - HTML tags
/// - Control characters
/// 
/// Args:
///     text: The input text to clean
/// 
/// Returns:
///     Cleaned text
#[pyfunction]
fn clean_medical_text(text: &str) -> PyResult<String> {
    // Remove HTML tags (using pre-compiled regex)
    let text = HTML_RE.replace_all(text, "");
    
    // Remove control characters except newlines and tabs
    let text = CONTROL_RE.replace_all(&text, "");
    
    // Normalize whitespace
    let text = WHITESPACE_RE.replace_all(&text, " ");
    
    Ok(text.trim().to_string())
}


/// Parallel chunk processing for large documents
/// 
/// Args:
///     texts: List of texts to process
///     chunk_size: Maximum characters per chunk
///     overlap: Characters to overlap
/// 
/// Returns:
///     List of (original_index, chunks) tuples
/// 
/// Raises:
///     ValueError: If chunk_size is 0 or overlap >= chunk_size
#[pyfunction]
#[pyo3(signature = (texts, chunk_size=1000, overlap=200))]
fn parallel_chunk_texts(texts: Vec<String>, chunk_size: usize, overlap: usize) -> PyResult<Vec<(usize, Vec<String>)>> {
    // Validate parameters once
    if chunk_size == 0 {
        return Err(PyValueError::new_err("chunk_size must be greater than 0"));
    }
    if overlap >= chunk_size {
        return Err(PyValueError::new_err("overlap must be less than chunk_size"));
    }
    
    // Process in parallel - chunk_text now returns PyResult, so we unwrap safely
    // since we already validated parameters
    let results: Vec<(usize, Vec<String>)> = texts
        .par_iter()
        .enumerate()
        .map(|(idx, text)| {
            // Safe to unwrap here because we validated params above
            let chunks = chunk_text_internal(text, chunk_size, overlap);
            (idx, chunks)
        })
        .collect();
    
    Ok(results)
}

/// Internal chunk_text that doesn't return PyResult (for parallel processing)
fn chunk_text_internal(text: &str, chunk_size: usize, overlap: usize) -> Vec<String> {
    if text.is_empty() {
        return vec![];
    }
    
    let sentences: Vec<&str> = text.split(|c| c == '.' || c == '\n').collect();
    let mut chunks: Vec<String> = Vec::new();
    let mut current_chunk = String::new();
    
    for sentence in sentences {
        let sentence = sentence.trim();
        if sentence.is_empty() {
            continue;
        }
        
        if current_chunk.len() + sentence.len() + 2 > chunk_size && !current_chunk.is_empty() {
            chunks.push(current_chunk.clone());
            
            let overlap_start = if current_chunk.len() > overlap {
                current_chunk.len() - overlap
            } else {
                0
            };
            current_chunk = current_chunk[overlap_start..].to_string();
        }
        
        if !current_chunk.is_empty() {
            current_chunk.push_str(". ");
        }
        current_chunk.push_str(sentence);
    }
    
    if !current_chunk.is_empty() {
        chunks.push(current_chunk);
    }
    
    chunks
}


/// Extract medical entities (regex-based)
/// 
/// Extracts:
/// - Dates (DD/MM/YYYY, DD-MM-YYYY)
/// - Times (HH:MM, HH:MM:SS)
/// - Measurements (numbers with units: mg, ml, g, kg, mmHg, etc.)
/// 
/// Args:
///     text: The input text
/// 
/// Returns:
///     Dict with extracted entities: {"dates": [...], "times": [...], "measurements": [...]}
#[pyfunction]
fn extract_entities(text: &str) -> PyResult<std::collections::HashMap<String, Vec<String>>> {
    let mut entities: std::collections::HashMap<String, Vec<String>> = std::collections::HashMap::new();
    
    // Dates (using pre-compiled regex)
    entities.insert(
        "dates".to_string(),
        DATE_RE.find_iter(text).map(|m| m.as_str().to_string()).collect()
    );
    
    // Times
    entities.insert(
        "times".to_string(),
        TIME_RE.find_iter(text).map(|m| m.as_str().to_string()).collect()
    );
    
    // Measurements (number + unit)
    entities.insert(
        "measurements".to_string(),
        MEASURE_RE.find_iter(text).map(|m| m.as_str().to_string()).collect()
    );
    
    Ok(entities)
}


/// Python module definition
#[pymodule]
fn ferro_engine(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(chunk_text, m)?)?;
    m.add_function(wrap_pyfunction!(tokenize, m)?)?;
    m.add_function(wrap_pyfunction!(count_tokens, m)?)?;
    m.add_function(wrap_pyfunction!(clean_medical_text, m)?)?;
    m.add_function(wrap_pyfunction!(parallel_chunk_texts, m)?)?;
    m.add_function(wrap_pyfunction!(extract_entities, m)?)?;
    
    // Module metadata - v3.0.0 FERRO compliant
    m.add("__version__", "3.0.0")?;
    m.add("__doc__", "FERRO Protocol v3.0.0 - Rust CPU-bound engine for text processing")?;
    
    Ok(())
}


#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_chunk_text_empty() {
        let result = chunk_text_internal("", 100, 20);
        assert!(result.is_empty());
    }

    #[test]
    fn test_chunk_text_basic() {
        let text = "First sentence. Second sentence. Third sentence.";
        let result = chunk_text_internal(text, 50, 10);
        assert!(!result.is_empty());
    }

    #[test]
    fn test_clean_medical_text() {
        let text = "<b>Test</b>  multiple   spaces";
        let result = clean_medical_text(text).unwrap();
        assert_eq!(result, "Test multiple spaces");
    }

    #[test]
    fn test_extract_entities() {
        let text = "Fecha: 15/01/2026 a las 14:30. Dosis: 500mg";
        let result = extract_entities(text).unwrap();
        assert_eq!(result.get("dates").unwrap().len(), 1);
        assert_eq!(result.get("times").unwrap().len(), 1);
        assert_eq!(result.get("measurements").unwrap().len(), 1);
    }
}
