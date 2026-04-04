import asyncio
from app.adapters.mongo_client import get_mongo_db

async def check():
    db = get_mongo_db()
    cursor = db.golden_rules.find({})
    async for doc in cursor:
        rules = doc.get("rules", [])
        _id = doc.get("_id")
        title = doc.get("title")
        print(f"[{_id}] ({title}): {len(rules)} rules")

asyncio.run(check())
