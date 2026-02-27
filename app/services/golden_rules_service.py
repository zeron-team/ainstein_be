"""
Golden Rules Service — Loads active rules from MongoDB for injection into LLM prompts.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.adapters.mongo_client import get_mongo_db

log = logging.getLogger(__name__)


async def get_golden_rules_for_prompt() -> str:
    """
    Loads all active golden rules from MongoDB and formats them
    as a block of text to inject into the LLM system prompt.

    Returns:
        String with formatted rules, or empty string if no rules.
    """
    try:
        mongo = get_mongo_db()
        cursor = mongo.golden_rules.find({})

        sections = []
        async for doc in cursor:
            key = doc["_id"]
            title = doc.get("title", key)
            rules = doc.get("rules", [])

            # Filter only active AND processed rules
            active_rules = [r for r in rules if r.get("active", True) and r.get("processed", False)]

            if not active_rules:
                continue

            # Format rules by priority
            lines = []
            for r in active_rules:
                priority = r.get("priority", "normal")
                text = r.get("text", "").strip()
                if not text:
                    continue

                if priority == "critica":
                    lines.append(f"  ⛔ CRÍTICA: {text}")
                elif priority == "alta":
                    lines.append(f"  ⚠️ ALTA: {text}")
                else:
                    lines.append(f"  • {text}")

            if lines:
                sections.append(f"\n--- {title.upper()} ---\n" + "\n".join(lines))

        if not sections:
            return ""

        header = """

################################################################################
#   🏆 REGLAS DE ORO (Golden Rules) - CONFIGURADAS POR EL EQUIPO MÉDICO       #
#   Estas reglas tienen PRIORIDAD MÁXIMA y deben aplicarse SIEMPRE.            #
################################################################################
"""
        result = header + "\n".join(sections) + "\n"

        log.info("[GoldenRules] Loaded %d sections with active rules (%d chars)",
                 len(sections), len(result))
        return result

    except Exception as e:
        log.warning("[GoldenRules] Error loading rules: %s", e)
        return ""
