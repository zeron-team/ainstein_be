import asyncio
from app.adapters.mongo_client import get_mongo_db
import json

async def dump_evolucion():
    db = get_mongo_db()
    doc = await db.golden_rules.find_one({"_id": "evolucion"})
    if doc:
        rules = doc.get("rules", [])
        with open("/tmp/evolucion_rules_114.json", "w", encoding="utf-8") as f:
            json.dump([r.get("text", "") for r in rules], f, indent=2, ensure_ascii=False)
        print(f"Dumped {len(rules)} rules to /tmp/evolucion_rules_114.json")

asyncio.run(dump_evolucion())
