"""
Golden Rules Service — Loads active rules from MongoDB for injection into LLM prompts.
Includes priority-based truncation to stay within context window limits.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.adapters.mongo_client import get_mongo_db

log = logging.getLogger(__name__)

# Max chars for the golden rules block injected into the prompt.
# With 593+ rules this prevents blowing up the LLM context window.
MAX_PROMPT_CHARS = 15_000

# Priority ordering: critical first, then alta, then normal
PRIORITY_ORDER = {"critica": 0, "alta": 1, "normal": 2}


async def get_golden_rules_for_prompt() -> str:
    """
    Loads all active + processed golden rules from MongoDB, formats them
    as a block of text, and truncates by priority if over MAX_PROMPT_CHARS.

    Returns:
        String with formatted rules, or empty string if no rules.
    """
    try:
        mongo = get_mongo_db()
        cursor = mongo.golden_rules.find({})

        # Collect all rules across sections with metadata
        all_rules = []
        async for doc in cursor:
            key = doc["_id"]
            title = doc.get("title", key)
            rules = doc.get("rules", [])

            # Filter only active AND processed rules
            for r in rules:
                if r.get("active", True) and r.get("processed", False):
                    text = r.get("text", "").strip()
                    if text:
                        priority = r.get("priority", "normal")
                        all_rules.append({
                            "section": title,
                            "priority": priority,
                            "text": text,
                            "sort_key": PRIORITY_ORDER.get(priority, 9),
                        })

        if not all_rules:
            return ""

        # Sort: critical first, then alta, then normal
        all_rules.sort(key=lambda r: r["sort_key"])

        # Build output grouped by section, respecting char limit
        header = """
################################################################################
#   🏆 REGLAS DE ORO (Golden Rules) - CONFIGURADAS POR EL EQUIPO MÉDICO       #
#   Estas reglas tienen PRIORIDAD MÁXIMA y deben aplicarse SIEMPRE.            #
################################################################################
"""
        # Group rules by section preserving priority order
        from collections import OrderedDict
        sections: OrderedDict[str, list[str]] = OrderedDict()
        total_chars = len(header)
        included = 0
        skipped = 0

        for r in all_rules:
            if r["priority"] == "critica":
                line = f"  ⛔ CRÍTICA: {r['text']}"
            elif r["priority"] == "alta":
                line = f"  ⚠️ ALTA: {r['text']}"
            else:
                line = f"  • {r['text']}"

            # Check if adding this rule would exceed the limit
            line_cost = len(line) + 1  # +1 for newline
            section_title = r["section"]
            if section_title not in sections:
                line_cost += len(f"\n--- {section_title.upper()} ---\n")

            if total_chars + line_cost > MAX_PROMPT_CHARS:
                skipped += 1
                continue

            if section_title not in sections:
                sections[section_title] = []
                total_chars += len(f"\n--- {section_title.upper()} ---\n")

            sections[section_title].append(line)
            total_chars += len(line) + 1
            included += 1

        # Assemble final text
        parts = []
        for title, lines in sections.items():
            parts.append(f"\n--- {title.upper()} ---\n" + "\n".join(lines))

        result = header + "\n".join(parts) + "\n"

        log.info(
            "[GoldenRules] Loaded %d rules in %d sections (%d chars, skipped %d low-priority)",
            included, len(sections), len(result), skipped,
        )
        return result

    except Exception as e:
        log.warning("[GoldenRules] Error loading rules: %s", e)
        return ""
