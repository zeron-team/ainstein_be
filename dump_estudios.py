import asyncio
from app.adapters.mongo_client import get_mongo_db
import json

async def dump_estudios():
    db = get_mongo_db()
    doc = await db.golden_rules.find_one({"_id": "estudios"})
    if doc:
        rules = doc.get("rules", [])
        with open("/tmp/estudios_72.json", "w", encoding="utf-8") as f:
            json.dump([r.get("text", "") for r in rules], f, indent=2, ensure_ascii=False)
        print("Dumped rules to /tmp/estudios_72.json")
    else:
        print("No document found for estudios.")

asyncio.run(dump_estudios())
