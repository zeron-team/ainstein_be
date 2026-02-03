# app/domain/interfaces/feedback_interface.py
"""
Interface para servicios de feedback.

Principio SOLID: D (Dependency Inversion)
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass


@dataclass
class FeedbackEntry:
    """Entrada de feedback."""
    epc_id: str
    section: str
    rating: str  # "ok", "partial", "bad"
    feedback_text: Optional[str] = None
    has_omissions: Optional[bool] = None
    has_repetitions: Optional[bool] = None
    is_confusing: Optional[bool] = None


class IFeedbackService(ABC):
    """
    Interface abstracta para gestión de feedback.
    
    Implementaciones:
    - app.services.epc.feedback_service.EPCFeedbackService
    """
    
    @abstractmethod
    def validate(self, entry: FeedbackEntry) -> None:
        """
        Valida una entrada de feedback.
        
        Raises:
            ValueError: Si los datos son inválidos
        """
        pass
    
    @abstractmethod
    async def submit(
        self,
        entry: FeedbackEntry,
        user_id: Optional[str],
        user_name: str,
        patient_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Guarda feedback.
        
        Returns:
            {"ok": True, "message": "..."}
        """
        pass
    
    @abstractmethod
    async def get_user_feedback(
        self,
        epc_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Obtiene feedback previo de un usuario para una EPC.
        
        Returns:
            {"sections": {...}, "has_previous": bool}
        """
        pass
    
    @abstractmethod
    async def get_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas de feedback.
        
        Returns:
            {"by_section": {...}, "total": N}
        """
        pass
