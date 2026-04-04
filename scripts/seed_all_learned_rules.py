#!/usr/bin/env python3
"""
Parse REGLAS_EPC.md and seed ALL 593 individual learned rules into MongoDB.

Each rule is inserted individually so doctors can audit, edit, enable/disable
them from the frontend. Rules are grouped by section.

Usage:
    cd ainstein_be
    source .venv/bin/activate && python scripts/seed_all_learned_rules.py
"""

import asyncio
import re
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.adapters.mongo_client import get_mongo_db

# Map markdown section headers to MongoDB section keys
SECTION_MAP = {
    "Estudios": "estudios",
    "Evolución": "evolucion",
    "Indicaciones al Alta": "indicaciones_alta",
    "Interconsultas": "interconsultas",
    "Medicación": "medicacion",
    "Motivo de Internación": "motivo_internacion",
    "Procedimientos": "procedimientos",
    "Recomendaciones": "recomendaciones",
}

SECTION_TITLES = {
    "estudios": "Estudios",
    "evolucion": "Evolución",
    "indicaciones_alta": "Indicaciones al Alta",
    "interconsultas": "Interconsultas",
    "medicacion": "Medicación",
    "motivo_internacion": "Motivo de Internación",
    "procedimientos": "Procedimientos",
    "recomendaciones": "Recomendaciones",
}

MD_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "docs", "REGLAS_EPC.md"
)


def parse_rules_from_md(filepath: str) -> dict[str, list[dict]]:
    """Parse REGLAS_EPC.md and extract individual rules per section."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Split into sections by "### 📌 <Section Name>"
    section_pattern = re.compile(r"### 📌\s+(.+?)\s+\(\d+ reglas\)")
    parts = section_pattern.split(content)

    rules_by_section: dict[str, list[dict]] = {}
    
    i = 1
    while i < len(parts) - 1:
        section_name = parts[i].strip()
        section_body = parts[i + 1]
        i += 2

        section_key = SECTION_MAP.get(section_name)
        if not section_key:
            print(f"  ⚠️  Unknown section: '{section_name}', skipping")
            continue

        # Extract individual rules: **N. Rule text.**\n✅ Estado: applied | ...
        rule_pattern = re.compile(
            r"\*\*(\d+)\.\s+(.+?)\*\*\s*\n\s*[✅🔍]\s*Estado:\s*(applied|detected)\s*\|\s*Detectada\s+(\d+)x\s*\|\s*Fecha:\s*(\S+)",
            re.DOTALL
        )

        section_rules = []
        for match in rule_pattern.finditer(section_body):
            rule_num = int(match.group(1))
            rule_text = match.group(2).strip()
            status = match.group(3)
            frequency = int(match.group(4))
            date_str = match.group(5)

            # Clean up multi-line rule text
            rule_text = re.sub(r"\s+", " ", rule_text).strip()
            # Remove trailing "  " or similar
            rule_text = rule_text.rstrip()

            # Assign priority based on frequency
            if frequency >= 5:
                priority = "critica"
            elif frequency >= 3:
                priority = "alta"
            else:
                priority = "normal"

            section_rules.append({
                "text": rule_text,
                "priority": priority,
                "active": True,
                "processed": True,
                "source": "learned_from_feedback",
                "status": status,
                "frequency": frequency,
                "learned_date": date_str,
                "rule_number": rule_num,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

        rules_by_section[section_key] = section_rules
        print(f"  📂 {section_name}: {len(section_rules)} reglas parseadas")

    return rules_by_section


async def seed():
    print("=" * 70)
    print("  SEED: All 593 Individual Learned Rules → MongoDB Golden Rules")
    print("  Source: docs/REGLAS_EPC.md")
    print("=" * 70)

    if not os.path.exists(MD_PATH):
        print(f"  ❌ File not found: {MD_PATH}")
        return

    print(f"\n📖 Parsing {MD_PATH}...\n")
    rules_by_section = parse_rules_from_md(MD_PATH)

    total_parsed = sum(len(r) for r in rules_by_section.values())
    print(f"\n📊 Total parsed: {total_parsed} reglas en {len(rules_by_section)} secciones\n")

    db = get_mongo_db()

    total_added = 0
    total_skipped = 0

    for section_key, new_rules in rules_by_section.items():
        title = SECTION_TITLES.get(section_key, section_key)

        existing = await db.golden_rules.find_one({"_id": section_key})

        if existing:
            existing_rules = existing.get("rules", [])
            # Build set of existing rule texts (lowercased, first 80 chars) for dedup
            existing_texts = set()
            for r in existing_rules:
                txt = r.get("text", "").strip().lower()[:80]
                existing_texts.add(txt)

            added = 0
            for rule in new_rules:
                key = rule["text"].strip().lower()[:80]
                if key not in existing_texts:
                    rule["id"] = f"{section_key}_learned_{rule['rule_number']}"
                    existing_rules.append(rule)
                    existing_texts.add(key)
                    added += 1

            await db.golden_rules.update_one(
                {"_id": section_key},
                {"$set": {
                    "rules": existing_rules,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }},
            )
            total_added += added
            total_skipped += len(new_rules) - added
            print(f"  ✅ {title}: +{added} new (skipped {len(new_rules) - added} duplicates, total now {len(existing_rules)})")
        else:
            # Create new section
            for rule in new_rules:
                rule["id"] = f"{section_key}_learned_{rule['rule_number']}"

            doc = {
                "_id": section_key,
                "title": title,
                "rules": new_rules,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.golden_rules.insert_one(doc)
            total_added += len(new_rules)
            print(f"  🆕 {title}: Created with {len(new_rules)} rules")

    print(f"\n{'=' * 70}")
    print(f"  🏆 DONE! Added {total_added} new rules, skipped {total_skipped} duplicates.")
    print(f"  All rules have processed=True so they take effect immediately.")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    asyncio.run(seed())
