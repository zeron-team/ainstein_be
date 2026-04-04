import asyncio
from app.adapters.mongo_client import get_mongo_db
import json

async def dump_all():
    db = get_mongo_db()
    sections = ["procedimientos", "interconsultas", "medicacion", "indicaciones_alta", "recomendaciones"]
    
    dump_data = {}
    for sec in sections:
        doc = await db.golden_rules.find_one({"_id": sec})
        if doc:
            rules = doc.get("rules", [])
            dump_data[sec] = [r.get("text", "") for r in rules]
            print(f"[{sec}] {len(rules)} rules.")
            
    with open("/tmp/remaining_rules.json", "w", encoding="utf-8") as f:
        json.dump(dump_data, f, indent=2, ensure_ascii=False)
    print("Dumped all to /tmp/remaining_rules.json")

asyncio.run(dump_all())
