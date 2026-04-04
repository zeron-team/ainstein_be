import asyncio
from typing import List, Dict, Any
from app.adapters.mongo_client import get_mongo_db
from datetime import datetime

async def test_get_all_rules():
    mongo = get_mongo_db()
    cursor = mongo.golden_rules.find({})
    sections = []
    total_golden = 0
    async for doc in cursor:
        rules = doc.get("rules", [])
        total_golden += len(rules)
        sections.append({
            "key": doc["_id"],
            "title": doc.get("title", doc["_id"]),
            "rules": rules,
        })
    print(f"Total pure golden rules: {total_golden}")
    
    SECTION_LABELS = {
        "interconsultas": "Interconsultas",
        "EXCLUDE": "🚫 Excluir",
    }
    
    dict_cursor = mongo.section_mapping_dictionary.find().sort("frequency", -1).limit(200)
    seen = {}
    async for doc in dict_cursor:
        item = doc.get("item_pattern", "")
        target = doc.get("target_section", "")
        freq = doc.get("frequency", 1)
        key = (item.upper().strip(), target)
        if key in seen: continue
        target_label = SECTION_LABELS.get(target, target)
        seen[key] = True
    
    print(f"Total dictionary rules (learned): {len(seen)}")
    print(f"GRAND TOTAL returned: {total_golden + len(seen)}")

if __name__ == "__main__":
    asyncio.run(test_get_all_rules())
