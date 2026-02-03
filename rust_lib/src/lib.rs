use pyo3::prelude::*;

#[pyfunction]
fn chunk_text(text: String, chunk_size: usize) -> PyResult<Vec<String>> {
    let mut chunks = Vec::new();
    let mut current_chunk = String::new();
    
    // Naive split by Words for now, simpler than tokenizers crate setup for this proof of concept
    // In production this would use tokenizers or more robust logic
    for word in text.split_whitespace() {
        if current_chunk.len() + word.len() + 1 > chunk_size {
            chunks.push(current_chunk.clone());
            current_chunk.clear();
        }
        if !current_chunk.is_empty() {
            current_chunk.push(' ');
        }
        current_chunk.push_str(word);
    }
    if !current_chunk.is_empty() {
        chunks.push(current_chunk);
    }
    
    Ok(chunks)
}

#[pymodule]
fn ainstein_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(chunk_text, m)?)?;
    Ok(())
}
