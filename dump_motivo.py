import asyncio
from app.adapters.mongo_client import get_mongo_db
import json

async def get_motivos():
    db = get_mongo_db()
    # Find the Golden Rule document
    doc = await db.golden_rules.find_one({"_id": "motivo"})
    if not doc:
        doc = await db.golden_rules.find_one({"key": "motivo"})
        
    if doc:
        rules = doc.get("rules", [])
        print(f"FOUND {len(rules)} RULES FOR MOTIVO")
        # Save to file for easy reading
        with open("/tmp/motivo_rules.json", "w") as f:
            json.dump([r.get("text", "") for r in rules], f, indent=2, ensure_ascii=False)
        print("Rules saved to /tmp/motivo_rules.json")
    else:
        print("No document found for motivo.")

asyncio.run(get_motivos())
