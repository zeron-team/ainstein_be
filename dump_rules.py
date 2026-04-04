import asyncio
import json
from app.adapters.mongo_client import get_mongo_db

async def get_all():
    db = get_mongo_db()
    docs = await db.golden_rules.find({}).to_list(None)
    for d in docs:
        d["_id"] = str(d["_id"])
    with open("/tmp/db_rules_dump.json", "w") as f:
        json.dump(docs, f, indent=2)

if __name__ == "__main__":
    asyncio.run(get_all())
