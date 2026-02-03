# backend/app/services/llm_usage_tracker.py
"""
Servicio de Tracking de Uso de LLM.

Registra cada llamada a LLM para calcular costos y estadísticas.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from bson import ObjectId

from app.adapters.mongo_client import db as mongo

log = logging.getLogger(__name__)

# Pricing de Gemini (USD por 1M tokens) - Enero 2024
GEMINI_PRICING = {
    "gemini-2.5-pro-preview-05-06": {
        "input": 1.25,    # $1.25 per 1M input tokens
        "output": 10.00,  # $10.00 per 1M output tokens
    },
    "gemini-2.5-pro": {
        "input": 1.25,
        "output": 10.00,
    },
    "gemini-2.0-flash": {
        "input": 0.075,   # $0.075 per 1M input tokens
        "output": 0.30,   # $0.30 per 1M output tokens
    },
    "gemini-1.5-flash": {
        "input": 0.075,
        "output": 0.30,
    },
    "gemini-1.5-pro": {
        "input": 1.25,
        "output": 5.00,
    },
    "default": {
        "input": 0.10,
        "output": 0.40,
    }
}


class LLMUsageTracker:
    """Tracker de uso y costos de LLM."""
    
    def __init__(self):
        self.collection = mongo.llm_usage
    
    def calculate_cost(
        self, 
        model: str, 
        input_tokens: int, 
        output_tokens: int
    ) -> float:
        """Calcula el costo en USD basado en tokens."""
        pricing = GEMINI_PRICING.get(model, GEMINI_PRICING["default"])
        
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        
        return round(input_cost + output_cost, 6)
    
    async def track_usage(
        self,
        operation_type: str,  # "epc_generation" | "learning_analysis"
        model: str,
        input_tokens: int,
        output_tokens: int,
        epc_id: Optional[str] = None,
        section: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> str:
        """
        Registra uso de LLM.
        
        Args:
            operation_type: Tipo de operación
            model: Modelo usado
            input_tokens: Tokens de entrada
            output_tokens: Tokens de salida
            epc_id: ID del EPC (si aplica)
            section: Sección del EPC (si aplica)
            metadata: Datos adicionales
            
        Returns:
            ID del registro insertado
        """
        now = datetime.utcnow()
        total_tokens = input_tokens + output_tokens
        cost_usd = self.calculate_cost(model, input_tokens, output_tokens)
        
        doc = {
            "timestamp": now,
            "date": now.strftime("%Y-%m-%d"),
            "operation_type": operation_type,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "cost_usd": cost_usd,
            "epc_id": ObjectId(epc_id) if epc_id else None,
            "section": section,
            "metadata": metadata or {},
        }
        
        result = await self.collection.insert_one(doc)
        
        log.info(
            "[LLMUsageTracker] Tracked %s: %d tokens, $%.4f USD",
            operation_type, total_tokens, cost_usd
        )
        
        return str(result.inserted_id)
    
    async def get_daily_stats(
        self, 
        from_date: str, 
        to_date: str
    ) -> List[Dict[str, Any]]:
        """
        Obtiene estadísticas diarias de uso.
        
        Args:
            from_date: Fecha inicio (YYYY-MM-DD)
            to_date: Fecha fin (YYYY-MM-DD)
            
        Returns:
            Lista de estadísticas por día
        """
        pipeline = [
            {
                "$match": {
                    "date": {"$gte": from_date, "$lte": to_date}
                }
            },
            {
                "$group": {
                    "_id": {
                        "date": "$date",
                        "operation_type": "$operation_type"
                    },
                    "count": {"$sum": 1},
                    "total_tokens": {"$sum": "$total_tokens"},
                    "input_tokens": {"$sum": "$input_tokens"},
                    "output_tokens": {"$sum": "$output_tokens"},
                    "cost_usd": {"$sum": "$cost_usd"},
                }
            },
            {
                "$sort": {"_id.date": 1}
            }
        ]
        
        cursor = self.collection.aggregate(pipeline)
        results = await cursor.to_list(None)
        
        # Reorganizar por fecha
        by_date = {}
        for r in results:
            date = r["_id"]["date"]
            op_type = r["_id"]["operation_type"]
            
            if date not in by_date:
                by_date[date] = {
                    "date": date,
                    "epc_count": 0,
                    "learning_count": 0,
                    "total_tokens": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost_usd": 0.0,
                }
            
            if op_type == "epc_generation":
                by_date[date]["epc_count"] = r["count"]
            elif op_type == "learning_analysis":
                by_date[date]["learning_count"] = r["count"]
            
            by_date[date]["total_tokens"] += r["total_tokens"]
            by_date[date]["input_tokens"] += r["input_tokens"]
            by_date[date]["output_tokens"] += r["output_tokens"]
            by_date[date]["cost_usd"] += r["cost_usd"]
        
        # Redondear costos
        for d in by_date.values():
            d["cost_usd"] = round(d["cost_usd"], 4)
        
        return sorted(by_date.values(), key=lambda x: x["date"])
    
    async def get_summary(
        self, 
        from_date: Optional[str] = None, 
        to_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Obtiene resumen total de uso.
        
        Args:
            from_date: Fecha inicio opcional
            to_date: Fecha fin opcional
            
        Returns:
            Resumen con totales
        """
        match_stage = {}
        if from_date and to_date:
            match_stage["date"] = {"$gte": from_date, "$lte": to_date}
        
        pipeline = [
            {"$match": match_stage} if match_stage else {"$match": {}},
            {
                "$group": {
                    "_id": "$operation_type",
                    "count": {"$sum": 1},
                    "total_tokens": {"$sum": "$total_tokens"},
                    "input_tokens": {"$sum": "$input_tokens"},
                    "output_tokens": {"$sum": "$output_tokens"},
                    "cost_usd": {"$sum": "$cost_usd"},
                }
            }
        ]
        
        cursor = self.collection.aggregate(pipeline)
        results = await cursor.to_list(None)
        
        summary = {
            "total_epcs": 0,
            "total_learning": 0,
            "total_tokens": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_cost_usd": 0.0,
        }
        
        for r in results:
            if r["_id"] == "epc_generation":
                summary["total_epcs"] = r["count"]
            elif r["_id"] == "learning_analysis":
                summary["total_learning"] = r["count"]
            
            summary["total_tokens"] += r["total_tokens"]
            summary["input_tokens"] += r["input_tokens"]
            summary["output_tokens"] += r["output_tokens"]
            summary["total_cost_usd"] += r["cost_usd"]
        
        summary["total_cost_usd"] = round(summary["total_cost_usd"], 4)
        
        return summary
    
    async def get_model_breakdown(
        self, 
        from_date: Optional[str] = None, 
        to_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Obtiene desglose por modelo."""
        match_stage = {}
        if from_date and to_date:
            match_stage["date"] = {"$gte": from_date, "$lte": to_date}
        
        pipeline = [
            {"$match": match_stage} if match_stage else {"$match": {}},
            {
                "$group": {
                    "_id": "$model",
                    "count": {"$sum": 1},
                    "total_tokens": {"$sum": "$total_tokens"},
                    "cost_usd": {"$sum": "$cost_usd"},
                }
            },
            {"$sort": {"cost_usd": -1}}
        ]
        
        cursor = self.collection.aggregate(pipeline)
        results = await cursor.to_list(None)
        
        return [
            {
                "model": r["_id"],
                "calls": r["count"],
                "tokens": r["total_tokens"],
                "cost_usd": round(r["cost_usd"], 4),
            }
            for r in results
        ]


# Singleton
_tracker_instance: Optional[LLMUsageTracker] = None


def get_llm_usage_tracker() -> LLMUsageTracker:
    """Obtiene instancia singleton del tracker."""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = LLMUsageTracker()
    return _tracker_instance
