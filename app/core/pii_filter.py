# app/core/pii_filter.py
"""
FERRO D2 v3.0.0 - PII Filter for MongoDB Logging

Sanitizes sensitive data before logging to MongoDB (fire & forget storage).

FERRO D2 Requirement:
- MongoDB logs must NOT contain raw PII
- Sensitive fields are redacted or hashed
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Set

# Fields that should be completely redacted
REDACT_FIELDS: Set[str] = {
    "dni",
    "documento",
    "cuil",
    "cuit",
    "email",
    "correo",
    "telefono",
    "phone",
    "celular",
    "mobile",
    "direccion",
    "address",
    "domicilio",
    "password",
    "contraseña",
    "token",
    "api_key",
    "secret",
    "credit_card",
    "tarjeta",
    "cvv",
    "nro_beneficiario",
    "obra_social",
}

# Fields that should be partially masked (show last 4 chars)
MASK_FIELDS: Set[str] = {
    "dni",
    "cuil",
    "cuit",
    "telefono",
    "phone",
}

# Regex patterns for inline PII detection
PII_PATTERNS = [
    (r"\b\d{7,8}\b", "[DNI_REDACTED]"),  # DNI
    (r"\b\d{2}-\d{8}-\d{1}\b", "[CUIL_REDACTED]"),  # CUIL
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL_REDACTED]"),  # Email
    (r"\b(?:\+54|0)?(?:11|15)?\d{8}\b", "[PHONE_REDACTED]"),  # Phone AR
]


def hash_pii(value: str) -> str:
    """Create a one-way hash of PII for correlation without exposing data."""
    return f"hash:{hashlib.sha256(value.encode()).hexdigest()[:12]}"


def mask_value(value: str, visible_chars: int = 4) -> str:
    """Mask value showing only last N characters."""
    if len(value) <= visible_chars:
        return "*" * len(value)
    return "*" * (len(value) - visible_chars) + value[-visible_chars:]


def sanitize_for_mongo(data: Dict[str, Any], deep: bool = True) -> Dict[str, Any]:
    """
    Sanitize dictionary by redacting/masking PII fields.
    
    Args:
        data: Dictionary to sanitize
        deep: If True, recursively sanitize nested dicts
    
    Returns:
        Sanitized dictionary (copy, original unchanged)
    """
    if not isinstance(data, dict):
        return data
    
    result = {}
    
    for key, value in data.items():
        key_lower = key.lower()
        
        # Check if field should be redacted
        if key_lower in REDACT_FIELDS:
            if key_lower in MASK_FIELDS and isinstance(value, str):
                result[key] = mask_value(value)
            else:
                result[key] = "[REDACTED]"
        
        # Recursively sanitize nested dicts
        elif isinstance(value, dict) and deep:
            result[key] = sanitize_for_mongo(value, deep=True)
        
        # Sanitize lists of dicts
        elif isinstance(value, list) and deep:
            result[key] = [
                sanitize_for_mongo(item, deep=True) if isinstance(item, dict) else item
                for item in value
            ]
        
        # Sanitize strings for inline PII
        elif isinstance(value, str):
            result[key] = sanitize_text(value)
        
        else:
            result[key] = value
    
    return result


def sanitize_text(text: str) -> str:
    """
    Sanitize free-text by detecting and replacing PII patterns.
    
    Args:
        text: Text to sanitize
    
    Returns:
        Text with PII replaced by placeholders
    """
    result = text
    for pattern, replacement in PII_PATTERNS:
        result = re.sub(pattern, replacement, result)
    return result


def create_safe_log_entry(
    operation: str,
    tenant_id: str,
    user_id: str,
    data: Dict[str, Any],
    trace_id: str = None,
) -> Dict[str, Any]:
    """
    Create a sanitized log entry for MongoDB.
    
    Args:
        operation: Type of operation (e.g., "epc_generate", "patient_lookup")
        tenant_id: Tenant UUID
        user_id: User UUID
        data: Raw data to log (will be sanitized)
        trace_id: Optional trace ID for correlation
    
    Returns:
        Sanitized log entry ready for MongoDB
    """
    from datetime import datetime
    
    return {
        "operation": operation,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "trace_id": trace_id,
        "data": sanitize_for_mongo(data),
        "created_at": datetime.utcnow(),
    }
