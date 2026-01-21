# backend/app/services/feedback_insights_service.py
"""
Servicio de Insights de Feedback para Aprendizaje Continuo.

Extrae patrones y reglas del feedback de evaluadores para mejorar
la generación de EPCs futuras.

Flujo:
1. Agregar feedbacks por sección
2. Identificar secciones problemáticas (rating bad/partial)
3. Analizar textos de feedback para extraer patrones
4. Generar reglas dinámicas para el prompt de generación
5. Cachear insights para evitar recálculos frecuentes
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict

from app.adapters.mongo_client import db as mongo
from app.core.config import settings

log = logging.getLogger(__name__)

# Cache en memoria para insights (24h por defecto)
_insights_cache: Dict[str, Any] = {}
_cache_ttl_hours = 24


class FeedbackInsightsService:
    """
    Servicio que extrae insights del feedback para mejorar generación de EPCs.
    
    Características:
    - Agrega feedback por sección y rating
    - Extrae patrones comunes del feedback negativo
    - Genera reglas dinámicas para el LLM
    - Cachea resultados para performance
    """
    
    def __init__(self, cache_ttl_hours: int = 24):
        self.cache_ttl_hours = cache_ttl_hours
    
    async def get_insights(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Obtiene insights extraídos del feedback.
        
        Args:
            force_refresh: Si True, ignora el caché
        
        Returns:
            Diccionario con reglas, secciones problemáticas, y metadata
        """
        global _insights_cache
        
        # Verificar caché
        if not force_refresh and self._is_cache_valid():
            log.debug("[FeedbackInsights] Returning cached insights")
            return _insights_cache.get("data", {})
        
        # Calcular nuevos insights
        log.info("[FeedbackInsights] Computing fresh insights from feedback")
        
        try:
            insights = await self._compute_insights()
            
            # Actualizar caché
            _insights_cache = {
                "data": insights,
                "computed_at": datetime.utcnow(),
            }
            
            return insights
            
        except Exception as e:
            log.error("[FeedbackInsights] Error computing insights: %s", e)
            # Retornar caché antiguo si existe, o vacío
            return _insights_cache.get("data", self._empty_insights())
    
    async def _compute_insights(self) -> Dict[str, Any]:
        """Calcula insights desde MongoDB."""
        
        # 1. Obtener estadísticas por sección
        section_stats = await self._get_section_stats()
        
        # 2. Obtener feedbacks negativos con texto
        negative_feedbacks = await self._get_negative_feedbacks_with_text()
        
        # 3. Agrupar comentarios por sección
        comments_by_section = self._group_comments_by_section(negative_feedbacks)
        
        # 4. Obtener estadísticas de las 3 preguntas por sección
        questions_by_section = await self._get_questions_stats_by_section()
        
        # 5. Generar reglas desde los patrones (incluyendo las 3 preguntas)
        rules = self._generate_rules(section_stats, comments_by_section, questions_by_section)
        
        # 6. Identificar secciones problemáticas
        problem_sections = self._identify_problem_sections(section_stats)
        
        return {
            "rules": rules,
            "problem_sections": problem_sections,
            "section_stats": section_stats,
            "questions_by_section": questions_by_section,
            "total_feedbacks_analyzed": sum(
                s.get("total", 0) for s in section_stats.values()
            ),
            "computed_at": datetime.utcnow().isoformat(),
        }
    
    async def _get_section_stats(self) -> Dict[str, Dict[str, int]]:
        """Obtiene estadísticas de feedback por sección."""
        pipeline = [
            {
                "$group": {
                    "_id": {"section": "$section", "rating": "$rating"},
                    "count": {"$sum": 1}
                }
            }
        ]
        
        stats: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"ok": 0, "partial": 0, "bad": 0, "total": 0}
        )
        
        async for doc in mongo.epc_feedback.aggregate(pipeline):
            section = doc["_id"].get("section", "unknown")
            rating = doc["_id"].get("rating", "unknown")
            count = doc.get("count", 0)
            
            if rating in ("ok", "partial", "bad"):
                stats[section][rating] = count
                stats[section]["total"] += count
        
        return dict(stats)
    
    async def _get_negative_feedbacks_with_text(self, limit: int = 50) -> List[Dict]:
        """Obtiene feedbacks negativos que tienen texto de comentario."""
        cursor = mongo.epc_feedback.find(
            {
                "rating": {"$in": ["bad", "partial"]},
                "feedback_text": {"$ne": None, "$exists": True}
            },
            sort=[("created_at", -1)],
            limit=limit
        )
        
        return await cursor.to_list(limit)
    
    async def _get_questions_stats_by_section(self) -> Dict[str, Dict[str, int]]:
        """
        Obtiene estadísticas de las 3 preguntas obligatorias por sección.
        
        Returns:
            Dict con formato: {section: {omissions: N, repetitions: N, confusing: N}}
        """
        pipeline = [
            # Solo feedbacks negativos (donde se responden las 3 preguntas)
            {"$match": {"rating": {"$in": ["bad", "partial"]}}},
            {
                "$group": {
                    "_id": "$section",
                    "omissions": {
                        "$sum": {"$cond": [{"$eq": ["$has_omissions", True]}, 1, 0]}
                    },
                    "repetitions": {
                        "$sum": {"$cond": [{"$eq": ["$has_repetitions", True]}, 1, 0]}
                    },
                    "confusing": {
                        "$sum": {"$cond": [{"$eq": ["$is_confusing", True]}, 1, 0]}
                    },
                    "total_negative": {"$sum": 1},
                }
            }
        ]
        
        stats: Dict[str, Dict[str, int]] = {}
        
        async for doc in mongo.epc_feedback.aggregate(pipeline):
            section = doc.get("_id", "unknown")
            stats[section] = {
                "omissions": doc.get("omissions", 0),
                "repetitions": doc.get("repetitions", 0),
                "confusing": doc.get("confusing", 0),
                "total_negative": doc.get("total_negative", 0),
            }
        
        return stats
    
    def _group_comments_by_section(
        self, feedbacks: List[Dict]
    ) -> Dict[str, List[str]]:
        """Agrupa comentarios de feedback por sección."""
        grouped: Dict[str, List[str]] = defaultdict(list)
        
        for fb in feedbacks:
            section = fb.get("section", "unknown")
            text = (fb.get("feedback_text") or "").strip()
            if text:
                grouped[section].append(text)
        
        return dict(grouped)
    
    def _generate_rules(
        self,
        section_stats: Dict[str, Dict[str, int]],
        comments_by_section: Dict[str, List[str]],
        questions_by_section: Optional[Dict[str, Dict[str, int]]] = None,
    ) -> List[str]:
        """
        Genera reglas basadas en patrones de feedback.
        
        Estrategia:
        - Secciones con alto % de feedback negativo → generar advertencia
        - Patrones de las 3 preguntas (omisiones, repeticiones, confuso) → reglas específicas
        - Comentarios frecuentes → extraer patrón
        """
        rules = []
        questions_by_section = questions_by_section or {}
        
        for section, stats in section_stats.items():
            total = stats.get("total", 0)
            if total < 3:  # Mínimo 3 feedbacks para generar regla
                continue
            
            bad_count = stats.get("bad", 0)
            partial_count = stats.get("partial", 0)
            negative_rate = (bad_count + partial_count) / total if total > 0 else 0
            
            section_name = self._format_section_name(section)
            
            # Reglas basadas en las 3 preguntas obligatorias
            q_stats = questions_by_section.get(section, {})
            omissions = q_stats.get("omissions", 0)
            repetitions = q_stats.get("repetitions", 0)
            confusing = q_stats.get("confusing", 0)
            
            if omissions >= 2:
                rules.append(
                    f"En '{section_name}': Evitar OMISIONES. Se reportaron {omissions} casos de información faltante. "
                    "Incluir todos los datos relevantes de la HCE."
                )
            
            if repetitions >= 2:
                rules.append(
                    f"En '{section_name}': Evitar REPETICIONES. Se reportaron {repetitions} casos. "
                    "No repetir información ya mencionada en otras secciones."
                )
            
            if confusing >= 2:
                rules.append(
                    f"En '{section_name}': Evitar contenido CONFUSO/ERRÓNEO. Se reportaron {confusing} casos. "
                    "Verificar exactitud y claridad antes de incluir información."
                )
            
            # Si más del 30% es negativo, generar regla general
            if negative_rate > 0.3:
                comments = comments_by_section.get(section, [])
                
                # Regla genérica de alerta
                if bad_count > partial_count:
                    rules.append(
                        f"⚠️ Sección '{section_name}': Requiere atención especial. "
                        f"{bad_count} evaluaciones negativas ({int(negative_rate*100)}% del total)."
                    )
                
                # Extraer patrones de comentarios
                if comments:
                    pattern = self._extract_pattern_from_comments(comments[:5])
                    if pattern:
                        rules.append(
                            f"En '{section_name}': {pattern}"
                        )
        
        # Reglas generales basadas en feedback global
        if not rules:
            rules.append(
                "Mantener precisión clínica y evitar información no presente en la HCE."
            )
        
        return rules
    
    def _extract_pattern_from_comments(self, comments: List[str]) -> Optional[str]:
        """
        Extrae patrón común de una lista de comentarios.
        Versión simple: busca palabras clave frecuentes.
        """
        if not comments:
            return None
        
        # Palabras clave que indican problemas comunes
        keywords_negative = {
            "extenso": "ser más conciso",
            "largo": "reducir extensión",
            "falta": "incluir más detalle",
            "incompleto": "completar información faltante",
            "inventado": "usar solo datos de la HCE",
            "inventa": "no inventar información",
            "erróneo": "verificar precisión",
            "error": "revisar exactitud",
            "repite": "evitar repeticiones",
            "redundante": "eliminar redundancia",
            "confuso": "ser más claro",
            "vago": "ser más específico",
        }
        
        # Buscar keywords en comentarios
        combined = " ".join(comments).lower()
        for keyword, suggestion in keywords_negative.items():
            if keyword in combined:
                return suggestion
        
        # Si hay comentarios pero no keywords, usar el primero como guía
        if comments and len(comments[0]) < 100:
            return f"Feedback de evaluador: \"{comments[0]}\""
        
        return None
    
    def _identify_problem_sections(
        self, section_stats: Dict[str, Dict[str, int]]
    ) -> List[str]:
        """Identifica las secciones más problemáticas."""
        problems = []
        
        for section, stats in section_stats.items():
            total = stats.get("total", 0)
            if total < 3:
                continue
            
            bad_rate = stats.get("bad", 0) / total if total > 0 else 0
            if bad_rate > 0.2:  # Más del 20% malo
                problems.append(section)
        
        return sorted(problems)
    
    def _format_section_name(self, section: str) -> str:
        """Formatea nombre de sección para display."""
        mapping = {
            "motivo_internacion": "Motivo de Internación",
            "evolucion": "Evolución",
            "procedimientos": "Procedimientos",
            "interconsultas": "Interconsultas",
            "medicacion": "Medicación",
            "indicaciones_alta": "Indicaciones de Alta",
            "recomendaciones": "Recomendaciones",
            "diagnostico_principal": "Diagnóstico Principal",
            "diagnosticos_secundarios": "Diagnósticos Secundarios",
        }
        return mapping.get(section, section.replace("_", " ").title())
    
    def _is_cache_valid(self) -> bool:
        """Verifica si el caché es válido."""
        if "computed_at" not in _insights_cache:
            return False
        
        computed_at = _insights_cache["computed_at"]
        expiry = computed_at + timedelta(hours=self.cache_ttl_hours)
        return datetime.utcnow() < expiry
    
    def _empty_insights(self) -> Dict[str, Any]:
        """Retorna insights vacíos."""
        return {
            "rules": [],
            "problem_sections": [],
            "section_stats": {},
            "total_feedbacks_analyzed": 0,
            "computed_at": None,
        }
    
    def format_rules_for_prompt(self, insights: Dict[str, Any]) -> str:
        """
        Formatea las reglas para incluirlas en el prompt del LLM.
        
        Returns:
            String formateado para agregar al system prompt
        """
        rules = insights.get("rules", [])
        problem_sections = insights.get("problem_sections", [])
        
        if not rules and not problem_sections:
            return ""
        
        lines = [
            "",
            "IMPORTANTE - Aprendizaje de evaluaciones previas:",
        ]
        
        if problem_sections:
            sections_str = ", ".join(self._format_section_name(s) for s in problem_sections[:3])
            lines.append(f"Las siguientes secciones requieren especial atención: {sections_str}")
        
        if rules:
            lines.append("")
            lines.append("Reglas basadas en feedback de evaluadores:")
            for i, rule in enumerate(rules[:5], 1):  # Max 5 reglas
                lines.append(f"  {i}. {rule}")
        
        lines.append("")
        
        return "\n".join(lines)


# -----------------------------------------------------------------------------
# Singleton y funciones de conveniencia
# -----------------------------------------------------------------------------

_service_instance: Optional[FeedbackInsightsService] = None


def get_feedback_insights_service() -> FeedbackInsightsService:
    """Obtiene instancia singleton del servicio."""
    global _service_instance
    if _service_instance is None:
        _service_instance = FeedbackInsightsService()
    return _service_instance


async def get_prompt_rules() -> str:
    """
    Función de conveniencia para obtener reglas formateadas para prompt.
    
    Uso:
        rules = await get_prompt_rules()
        prompt = f"{system_prompt}\\n{rules}\\n..."
    """
    service = get_feedback_insights_service()
    insights = await service.get_insights()
    return service.format_rules_for_prompt(insights)
