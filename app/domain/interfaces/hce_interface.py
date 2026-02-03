# app/domain/interfaces/hce_interface.py
"""
Interface para extractores de HCE.

Principio SOLID: D (Dependency Inversion)
- Permite diferentes extractores según fuente de datos
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dataclasses import dataclass


@dataclass
class HCEContent:
    """Contenido estructurado extraído de HCE."""
    text: str
    source_type: str  # "ainstein", "pdf", "generic"
    patient_id: Optional[str] = None
    admission_id: Optional[str] = None
    fecha_ingreso: Optional[str] = None
    fecha_egreso: Optional[str] = None
    tipo_alta: Optional[str] = None


class IHCEExtractor(ABC):
    """
    Interface abstracta para extracción de texto de HCE.
    
    Implementaciones:
    - app.services.epc.hce_extractor.HCEExtractor
    - Futuro: PDFHCEExtractor, HL7HCEExtractor
    """
    
    @abstractmethod
    def extract(self, hce_doc: Dict[str, Any]) -> str:
        """
        Extrae texto clínico de un documento HCE.
        
        Args:
            hce_doc: Documento HCE de MongoDB
            
        Returns:
            Texto clínico extraído
        """
        pass
    
    @abstractmethod
    def extract_structured(self, hce_doc: Dict[str, Any]) -> HCEContent:
        """
        Extrae contenido estructurado de HCE.
        
        Args:
            hce_doc: Documento HCE de MongoDB
            
        Returns:
            HCEContent con texto y metadatos
        """
        pass
    
    @abstractmethod
    def detect_source_type(self, hce_doc: Dict[str, Any]) -> str:
        """
        Detecta el tipo de fuente de la HCE.
        
        Returns:
            "ainstein" | "pdf" | "generic"
        """
        pass
