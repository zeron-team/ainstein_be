# backend/app/services/feedback_llm_analyzer.py
"""
Servicio de Análisis de Feedback con LLM.

Usa LangChain con Gemini para analizar comentarios de evaluadores y generar
insights profesionales y específicos por sección.
"""

from __future__ import annotations

import logging
import json
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from app.core.config import settings
from app.adapters.mongo_client import db as mongo

log = logging.getLogger(__name__)

# Cache para análisis LLM (evitar llamadas repetidas)
_analysis_cache: Dict[str, Any] = {}
_cache_ttl_hours = 24


class FeedbackLLMAnalyzer:
    """Analizador de feedback usando LLM para generar insights profesionales."""
    
    SECTION_NAMES = {
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
    
    def __init__(self):
        self._llm = None
    
    def _get_llm(self):
        """Lazy load del cliente LLM usando LangChain."""
        if self._llm is None:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                
                self._llm = ChatGoogleGenerativeAI(
                    model=settings.GEMINI_MODEL or "gemini-2.0-flash",
                    google_api_key=settings.GEMINI_API_KEY,
                    temperature=0.3,  # Más determinístico para análisis
                )
                log.info("[FeedbackLLMAnalyzer] LangChain Gemini initialized")
            except Exception as e:
                log.error("[FeedbackLLMAnalyzer] Failed to init LangChain Gemini: %s", e)
                raise
        return self._llm
    
    async def analyze_all_sections(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Analiza todos los feedbacks y genera insights por sección.
        
        Returns:
            Diccionario con análisis por sección
        """
        global _analysis_cache
        
        # Verificar caché
        cache_key = "all_sections_analysis"
        if not force_refresh and self._is_cache_valid(cache_key):
            log.debug("[FeedbackLLMAnalyzer] Returning cached analysis")
            return _analysis_cache.get(cache_key, {}).get("data", {})
        
        log.info("[FeedbackLLMAnalyzer] Computing fresh LLM analysis")
        
        # Obtener todos los feedbacks con texto
        feedbacks = await self._get_all_feedbacks_with_text()
        
        if not feedbacks:
            return self._empty_analysis()
        
        # Agrupar por sección
        by_section = self._group_by_section(feedbacks)
        
        # Analizar cada sección con LLM
        sections_analysis = []
        for section_key, section_feedbacks in by_section.items():
            if len(section_feedbacks) < 1:
                continue
            
            analysis = await self._analyze_section(section_key, section_feedbacks)
            if analysis:
                sections_analysis.append(analysis)
        
        # Ordenar por porcentaje negativo
        sections_analysis.sort(
            key=lambda x: x.get("stats", {}).get("negative_pct", 0),
            reverse=True
        )
        
        result = {
            "sections": sections_analysis,
            "total_feedbacks_analyzed": len(feedbacks),
            "computed_at": datetime.utcnow().isoformat(),
        }
        
        # =====================================================
        # Registrar evento de aprendizaje en MongoDB
        # =====================================================
        try:
            learning_event = {
                "event_type": "llm_analysis",
                "timestamp": datetime.utcnow(),
                "feedbacks_analyzed": len(feedbacks),
                "sections_analyzed": len(sections_analysis),
                "total_problems_found": sum(len(s.get("problems", [])) for s in sections_analysis),
                "total_rules_generated": sum(len(s.get("rules", [])) for s in sections_analysis),
                "sections_summary": [
                    {
                        "section": s.get("name"),
                        "problems_count": len(s.get("problems", [])),
                        "rules_count": len(s.get("rules", [])),
                        "negative_pct": s.get("stats", {}).get("negative_pct", 0),
                    }
                    for s in sections_analysis
                ],
            }
            await mongo.learning_events.insert_one(learning_event)
            log.info("[FeedbackLLMAnalyzer] Learning event recorded: %d feedbacks, %d sections", 
                    len(feedbacks), len(sections_analysis))
        except Exception as e:
            log.warning("[FeedbackLLMAnalyzer] Failed to record learning event: %s", e)
        
        # Guardar en caché
        _analysis_cache[cache_key] = {
            "data": result,
            "computed_at": datetime.utcnow(),
        }
        
        return result
    
    async def _analyze_section(
        self, section_key: str, feedbacks: List[Dict]
    ) -> Optional[Dict[str, Any]]:
        """Analiza una sección específica con LLM."""
        
        section_name = self.SECTION_NAMES.get(section_key, section_key)
        
        # Separar por rating
        ok_feedbacks = [f for f in feedbacks if f.get("rating") == "ok"]
        partial_feedbacks = [f for f in feedbacks if f.get("rating") == "partial"]
        bad_feedbacks = [f for f in feedbacks if f.get("rating") == "bad"]
        
        total = len(feedbacks)
        ok_count = len(ok_feedbacks)
        partial_count = len(partial_feedbacks)
        bad_count = len(bad_feedbacks)
        
        # Extraer comentarios negativos
        negative_comments = []
        for f in (bad_feedbacks + partial_feedbacks):
            text = (f.get("feedback_text") or "").strip()
            if text:
                negative_comments.append({
                    "text": text,
                    "rating": f.get("rating"),
                    "evaluator": f.get("created_by_name", "Anónimo"),
                })
        
        # Si no hay comentarios negativos, retornar análisis básico
        if not negative_comments:
            return {
                "key": section_key,
                "name": section_name,
                "stats": {
                    "total": total,
                    "ok": ok_count,
                    "partial": partial_count,
                    "bad": bad_count,
                    "ok_pct": round((ok_count / total * 100) if total > 0 else 0, 1),
                    "negative_pct": round(((partial_count + bad_count) / total * 100) if total > 0 else 0, 1),
                },
                "problems": [],
                "rules": ["Mantener el enfoque actual - resultados positivos"],
                "summary": "Sin problemas significativos detectados",
            }
        
        # Llamar a LLM para análisis
        try:
            llm_analysis = await self._call_llm_analysis(section_name, negative_comments)
        except Exception as e:
            log.error("[FeedbackLLMAnalyzer] LLM analysis failed for %s: %s", section_key, e)
            llm_analysis = self._fallback_analysis(section_name, negative_comments)
        
        # Calcular estadísticas de las 3 preguntas
        omissions_count = sum(1 for f in feedbacks if f.get("has_omissions") == True)
        repetitions_count = sum(1 for f in feedbacks if f.get("has_repetitions") == True)
        confusing_count = sum(1 for f in feedbacks if f.get("is_confusing") == True)
        
        return {
            "key": section_key,
            "name": section_name,
            "stats": {
                "total": total,
                "ok": ok_count,
                "partial": partial_count,
                "bad": bad_count,
                "ok_pct": round((ok_count / total * 100) if total > 0 else 0, 1),
                "negative_pct": round(((partial_count + bad_count) / total * 100) if total > 0 else 0, 1),
            },
            "questions_stats": {
                "omissions": omissions_count,
                "repetitions": repetitions_count,
                "confusing": confusing_count,
            },
            "problems": llm_analysis.get("problems", []),
            "rules": llm_analysis.get("rules", []),
            "summary": llm_analysis.get("summary", ""),
        }
    
    async def _call_llm_analysis(
        self, section_name: str, comments: List[Dict]
    ) -> Dict[str, Any]:
        """Llama a LangChain Gemini para analizar los comentarios."""
        
        comments_text = "\n".join([
            f"- [{c['rating'].upper()}] \"{c['text']}\" (por {c['evaluator']})"
            for c in comments[:15]  # Máximo 15 comentarios
        ])
        
        prompt = f"""Eres un experto en calidad de documentación médica hospitalaria y Epicrisis.

CONTEXTO: La IA genera secciones de Epicrisis automáticamente. Los médicos evaluadores dan feedback marcando "OK", "Parcial" o "Malo" y dejando comentarios.

SECCIÓN A ANALIZAR: "{section_name}"

COMENTARIOS DE EVALUADORES:
{comments_text}

TU TAREA:
1. Identificar CATEGORÍAS de problemas recurrentes agrupando comentarios similares
2. Generar REGLAS TÉCNICAS ESPECÍFICAS que la IA debe seguir para mejorar

FORMATO DE RESPUESTA (JSON puro, sin markdown):
{{
    "problems": [
        {{
            "category": "Nombre técnico del problema EN ESPAÑOL",
            "count": número_de_menciones,
            "severity": "alta|media|baja",
            "examples": ["comentario ejemplo 1", "comentario ejemplo 2"]
        }}
    ],
    "rules": [
        "REGLA 1: [Regla específica y técnica para esta sección]",
        "REGLA 2: [Otra regla específica]"
    ],
    "summary": "Resumen de 1 línea del estado de esta sección EN ESPAÑOL"
}}

IMPORTANTE:
- RESPONDER TODO EN ESPAÑOL (categorías, reglas, resumen)
- Las reglas deben ser ESPECÍFICAS para "{section_name}", no genéricas
- Deben ser TÉCNICAS y ACCIONABLES
- Formato: "REGLA: [descripción clara de qué debe hacer o evitar la IA]"
- Ejemplos buenos:
  * "REGLA: Incluir duración exacta de antibióticos (ej: '7 días de Ceftriaxona 1g c/12h')"
  * "REGLA: Diferenciar medicación previa del paciente de la indicada durante internación"
  * "REGLA: Mencionar resultado de interconsultas, no solo que fueron solicitadas"
- Ejemplos malos (muy genéricos):
  * "Ser más específico"
  * "Incluir más información"
  * "Revisar los datos"

Responde SOLO el JSON en ESPAÑOL, sin explicaciones adicionales."""

        try:
            llm = self._get_llm()
            response = await llm.ainvoke(prompt)
            text = response.content.strip()
            
            # Limpiar markdown si viene
            if text.startswith("```"):
                lines = text.split("\n")
                # Encontrar líneas entre ``` y ```
                start = 1 if lines[0].startswith("```") else 0
                end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
                text = "\n".join(lines[start:end])
                if text.startswith("json"):
                    text = text[4:]
            
            result = json.loads(text.strip())
            
            # Trackear uso de tokens y costo
            try:
                from app.services.llm_usage_tracker import get_llm_usage_tracker
                tracker = get_llm_usage_tracker()
                
                # Estimar tokens (1 token ≈ 4 caracteres)
                input_tokens = len(prompt) // 4
                output_tokens = len(text) // 4
                
                await tracker.track_usage(
                    operation_type="learning_analysis",
                    model=settings.GEMINI_MODEL or "gemini-2.0-flash",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    section=section_name,
                    metadata={"comments_count": len(comments)},
                )
            except Exception as track_err:
                log.warning("[FeedbackLLMAnalyzer] Failed to track usage: %s", track_err)
            
            # Validar y calcular porcentajes
            if "problems" in result:
                total_mentions = sum(p.get("count", 1) for p in result.get("problems", []))
                for p in result.get("problems", []):
                    count = p.get("count", 1)
                    p["percentage"] = round((count / total_mentions * 100) if total_mentions > 0 else 0, 1)
            
            # Validar que hay reglas
            if not result.get("rules") or len(result.get("rules", [])) == 0:
                result["rules"] = self._generate_rules_from_problems(section_name, result.get("problems", []))
            
            log.info("[FeedbackLLMAnalyzer] Successfully analyzed %s with %d problems and %d rules", 
                    section_name, len(result.get("problems", [])), len(result.get("rules", [])))
            
            return result
            
        except json.JSONDecodeError as e:
            log.warning("[FeedbackLLMAnalyzer] Failed to parse LLM response: %s", e)
            return self._fallback_analysis(section_name, comments)
        except Exception as e:
            log.error("[FeedbackLLMAnalyzer] LLM call failed: %s", e)
            return self._fallback_analysis(section_name, comments)
    
    def _generate_rules_from_problems(self, section_name: str, problems: List[Dict]) -> List[str]:
        """Genera reglas básicas desde los problemas si LLM no las generó."""
        rules = []
        for p in problems[:3]:
            category = p.get("category", "")
            examples = p.get("examples", [])
            if category and examples:
                rule = f"REGLA: En {section_name}, evitar '{category}' - ejemplo: {examples[0][:60]}..."
                rules.append(rule)
        return rules if rules else [f"REGLA: Revisar feedback de evaluadores para mejorar {section_name}"]
    
    def _fallback_analysis(self, section_name: str, comments: List[Dict]) -> Dict[str, Any]:
        """Análisis de fallback con reglas específicas basadas en patrones."""
        
        # Analizar patrones en los comentarios para generar reglas específicas
        patterns = {
            "tiempo": ["tiempo", "duración", "días", "horas", "fecha"],
            "dosis": ["dosis", "mg", "ml", "gramos", "concentración"],
            "verificar": ["verificar", "comprobar", "revisar", "chequear"],
            "falta": ["falta", "no menciona", "omite", "no incluye"],
            "extenso": ["extenso", "largo", "demasiado", "resumir"],
            "inventado": ["inventado", "inventa", "no existe", "falso"],
        }
        
        detected_patterns = set()
        for c in comments:
            text_lower = c["text"].lower()
            for pattern_name, keywords in patterns.items():
                if any(kw in text_lower for kw in keywords):
                    detected_patterns.add(pattern_name)
        
        # Generar reglas específicas basadas en patrones
        rules = []
        pattern_rules = {
            "tiempo": f"REGLA: Incluir tiempos específicos en {section_name} (duración de tratamientos, fechas de procedimientos)",
            "dosis": f"REGLA: Especificar dosis completas con unidades (mg, ml) en {section_name}",
            "verificar": f"REGLA: Verificar datos clínicos contra la HCE antes de incluirlos en {section_name}",
            "falta": f"REGLA: Incluir toda la información relevante disponible en la HCE para {section_name}",
            "extenso": f"REGLA: Mantener {section_name} conciso, máximo 3-4 oraciones por concepto",
            "inventado": f"REGLA: NO generar información que no esté explícita en la HCE para {section_name}",
        }
        
        for pattern in detected_patterns:
            if pattern in pattern_rules:
                rules.append(pattern_rules[pattern])
        
        if not rules:
            rules = [f"REGLA: Revisar comentarios de evaluadores para mejorar {section_name}"]
        
        # Crear problemas desde los comentarios
        problems = [{
            "category": f"Problemas identificados en {section_name}",
            "count": len(comments),
            "severity": "alta" if len(comments) > 3 else "media",
            "percentage": 100,
            "examples": [c["text"][:100] for c in comments[:3]],
        }]
        
        return {
            "problems": problems,
            "rules": rules[:5],  # Máximo 5 reglas
            "summary": f"{len(comments)} comentarios negativos analizados con {len(detected_patterns)} patrones detectados",
        }
    
    async def _get_all_feedbacks_with_text(self, limit: int = 200) -> List[Dict]:
        """Obtiene todos los feedbacks con texto de comentario."""
        cursor = mongo.epc_feedback.find(
            {"feedback_text": {"$ne": None, "$exists": True}},
            sort=[("created_at", -1)],
            limit=limit
        )
        return await cursor.to_list(limit)
    
    def _group_by_section(self, feedbacks: List[Dict]) -> Dict[str, List[Dict]]:
        """Agrupa feedbacks por sección."""
        grouped = {}
        for fb in feedbacks:
            section = fb.get("section", "unknown")
            if section not in grouped:
                grouped[section] = []
            grouped[section].append(fb)
        return grouped
    
    def _is_cache_valid(self, key: str) -> bool:
        """Verifica si el caché es válido."""
        if key not in _analysis_cache:
            return False
        computed_at = _analysis_cache[key].get("computed_at")
        if not computed_at:
            return False
        expiry = computed_at + timedelta(hours=_cache_ttl_hours)
        return datetime.utcnow() < expiry
    
    def _empty_analysis(self) -> Dict[str, Any]:
        """Retorna análisis vacío."""
        return {
            "sections": [],
            "total_feedbacks_analyzed": 0,
            "computed_at": None,
        }


# Singleton
_analyzer_instance: Optional[FeedbackLLMAnalyzer] = None


def get_feedback_llm_analyzer() -> FeedbackLLMAnalyzer:
    """Obtiene instancia singleton del analizador."""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = FeedbackLLMAnalyzer()
    return _analyzer_instance


# Función para limpiar caché manualmente
def clear_insights_cache():
    """Limpia el caché de insights."""
    global _analysis_cache
    _analysis_cache = {}
    log.info("[FeedbackLLMAnalyzer] Cache cleared")
