# app/services/epc/feedback_service.py
"""
Servicio de Feedback de EPC.

Responsabilidad única: Gestionar feedback de secciones generadas por IA.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class FeedbackData:
    """Datos de feedback para una sección."""
    epc_id: str
    section: str
    rating: str  # "ok", "partial", "bad"
    feedback_text: Optional[str] = None
    original_content: Optional[str] = None
    has_omissions: Optional[bool] = None
    has_repetitions: Optional[bool] = None
    is_confusing: Optional[bool] = None


class FeedbackValidationError(Exception):
    """Error de validación de feedback."""
    pass


class EPCFeedbackService:
    """
    Servicio para gestionar feedback de EPC.
    
    Uso:
        service = EPCFeedbackService()
        await service.submit_feedback(feedback_data, user_id, user_name)
        stats = await service.get_stats()
    """
    
    VALID_RATINGS = ("ok", "partial", "bad")
    VALID_SECTIONS = (
        "motivo_internacion",
        "evolucion",
        "procedimientos",
        "interconsultas",
        "medicacion",
        "indicaciones_alta",
        "recomendaciones",
    )
    
    def validate_feedback(self, data: FeedbackData) -> None:
        """
        Valida los datos de feedback.
        
        Raises:
            FeedbackValidationError: Si los datos son inválidos
        """
        # Validar rating
        if data.rating not in self.VALID_RATINGS:
            raise FeedbackValidationError(
                f"Rating inválido '{data.rating}'. Usar: {', '.join(self.VALID_RATINGS)}"
            )
        
        # Validar sección (opcional pero recomendado)
        if data.section and data.section not in self.VALID_SECTIONS:
            log.warning(f"[Feedback] Sección no reconocida: {data.section}")
        
        # Para ratings negativos, validar campos requeridos
        if data.rating in ("partial", "bad"):
            if not (data.feedback_text or "").strip():
                raise FeedbackValidationError(
                    "El feedback es obligatorio para calificaciones 'a medias' o 'mal'"
                )
            
            if data.has_omissions is None or data.has_repetitions is None or data.is_confusing is None:
                raise FeedbackValidationError(
                    "Debe responder las 3 preguntas de evaluación (omisiones, repeticiones, confuso)"
                )
    
    async def submit_feedback(
        self,
        data: FeedbackData,
        user_id: Optional[str],
        user_name: str,
        patient_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Guarda feedback en MongoDB.
        
        Returns:
            {"ok": True, "message": "..."}
        """
        from app.adapters.mongo_client import db as mongo
        
        # Validar
        self.validate_feedback(data)
        
        # Construir documento
        feedback_doc = {
            "epc_id": data.epc_id,
            "patient_id": patient_id,
            "section": data.section,
            "rating": data.rating,
            "feedback_text": (data.feedback_text or "").strip() if data.feedback_text else None,
            "original_content": data.original_content,
            # Campos de preguntas (solo para ratings negativos)
            "has_omissions": data.has_omissions if data.rating in ("partial", "bad") else None,
            "has_repetitions": data.has_repetitions if data.rating in ("partial", "bad") else None,
            "is_confusing": data.is_confusing if data.rating in ("partial", "bad") else None,
            "created_by": user_id,
            "created_by_name": user_name,
            "created_at": datetime.utcnow(),
        }
        
        # Insertar
        await mongo.epc_feedback.insert_one(feedback_doc)
        
        log.info(
            "[Feedback] epc_id=%s section=%s rating=%s by=%s",
            data.epc_id, data.section, data.rating, user_name,
        )
        
        return {"ok": True, "message": "Feedback registrado correctamente"}
    
    async def get_user_feedback(
        self,
        epc_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Obtiene feedback previo del usuario para una EPC.
        
        Returns:
            {
                "sections": {section: {rating, feedback_text, created_at}},
                "evaluated_at": datetime,
                "has_previous": bool
            }
        """
        from app.adapters.mongo_client import db as mongo
        
        cursor = mongo.epc_feedback.find({
            "epc_id": epc_id,
            "created_by": user_id,
        }).sort("created_at", -1)
        
        feedbacks = await cursor.to_list(length=100)
        
        if not feedbacks:
            return {
                "sections": {},
                "evaluated_at": None,
                "has_previous": False,
            }
        
        # Agrupar por sección (última evaluación de cada una)
        sections = {}
        latest_date = None
        
        for fb in feedbacks:
            section = fb.get("section")
            if section and section not in sections:
                sections[section] = {
                    "rating": fb.get("rating"),
                    "feedback_text": fb.get("feedback_text"),
                    "created_at": fb.get("created_at"),
                    "has_omissions": fb.get("has_omissions"),
                    "has_repetitions": fb.get("has_repetitions"),
                    "is_confusing": fb.get("is_confusing"),
                }
                
                if not latest_date:
                    latest_date = fb.get("created_at")
        
        return {
            "sections": sections,
            "evaluated_at": latest_date,
            "has_previous": True,
        }
    
    async def get_stats_by_section(self) -> Dict[str, Any]:
        """
        Calcula estadísticas de feedback por sección.
        
        Returns:
            {
                "by_section": {section: {ok: N, partial: N, bad: N}},
                "total": N,
                "summary": {...}
            }
        """
        from app.adapters.mongo_client import db as mongo
        
        # Agregación por sección y rating
        pipeline = [
            {
                "$group": {
                    "_id": {"section": "$section", "rating": "$rating"},
                    "count": {"$sum": 1}
                }
            }
        ]
        
        cursor = mongo.epc_feedback.aggregate(pipeline)
        results = await cursor.to_list(length=100)
        
        # Estructurar por sección
        by_section: Dict[str, Dict[str, int]] = {}
        total = 0
        
        for r in results:
            section = r["_id"]["section"]
            rating = r["_id"]["rating"]
            count = r["count"]
            
            if section not in by_section:
                by_section[section] = {"ok": 0, "partial": 0, "bad": 0}
            
            by_section[section][rating] = count
            total += count
        
        # Calcular resumen
        total_ok = sum(s.get("ok", 0) for s in by_section.values())
        total_bad = sum(s.get("bad", 0) for s in by_section.values())
        
        return {
            "by_section": by_section,
            "total": total,
            "summary": {
                "approval_rate": round(total_ok / total * 100, 1) if total > 0 else 0,
                "rejection_rate": round(total_bad / total * 100, 1) if total > 0 else 0,
            }
        }


# Singleton
_feedback_service: Optional[EPCFeedbackService] = None


def get_feedback_service() -> EPCFeedbackService:
    """Obtiene instancia singleton del servicio de feedback."""
    global _feedback_service
    if _feedback_service is None:
        _feedback_service = EPCFeedbackService()
    return _feedback_service
