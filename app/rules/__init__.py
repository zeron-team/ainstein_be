# app/rules/__init__.py
"""
Módulo de reglas de negocio para EPC.
Implementación SOLID: Single Responsibility - cada regla en su módulo.
"""

from .death_detection import DeathDetectionRule, detect_death_in_text
from .medication_classifier import MedicationClassifier

__all__ = [
    "DeathDetectionRule",
    "detect_death_in_text",
    "MedicationClassifier",
]
