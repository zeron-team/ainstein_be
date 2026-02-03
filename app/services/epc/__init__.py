# app/services/epc/__init__.py
"""
Módulo de servicios EPC refactorizado según SOLID.

Este módulo extrae la lógica de negocio del router epc.py.

Estructura:
- helpers.py: Funciones auxiliares de parsing y formateo
- hce_extractor.py: Extracción de texto de HCE
- pdf_builder.py: Construcción de payload para PDF
- feedback_service.py: Gestión de feedback
"""

from .helpers import (
    clean_str,
    parse_dt_maybe,
    safe_objectid,
    uuid_str,
    json_from_ai,
    actor_name,
    age_from_ymd,
    list_to_lines,
    now,
)

from .hce_extractor import (
    HCEExtractor,
    extract_hce_text,
    extract_clinical_data,
    find_hce_by_id,
    find_latest_hce_for_patient,
)

from .pdf_builder import (
    EPCPDFBuilder,
    build_epc_pdf_payload,
)

from .feedback_service import (
    EPCFeedbackService,
    FeedbackData,
    FeedbackValidationError,
    get_feedback_service,
)

__all__ = [
    # Helpers
    "clean_str",
    "parse_dt_maybe",
    "safe_objectid",
    "uuid_str",
    "json_from_ai",
    "actor_name",
    "age_from_ymd",
    "list_to_lines",
    "now",
    # HCE
    "HCEExtractor",
    "extract_hce_text",
    "extract_clinical_data",
    "find_hce_by_id",
    "find_latest_hce_for_patient",
    # PDF
    "EPCPDFBuilder",
    "build_epc_pdf_payload",
    # Feedback
    "EPCFeedbackService",
    "FeedbackData",
    "FeedbackValidationError",
    "get_feedback_service",
]
