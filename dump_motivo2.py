import asyncio
from app.adapters.mongo_client import get_mongo_db
import json

async def dump():
    db = get_mongo_db()
    doc = await db.golden_rules.find_one({"_id": "motivo_internacion"})
    if doc:
        rules = doc.get("rules", [])
        with open("/tmp/motivo_internacion_88.json", "w", encoding="utf-8") as f:
            json.dump([r.get("text", "") for r in rules], f, indent=2, ensure_ascii=False)
        print("Dumped 88 rules to /tmp/motivo_internacion_88.json")

asyncio.run(dump())
