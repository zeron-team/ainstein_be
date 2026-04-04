import asyncio
from app.adapters.mongo_client import get_mongo_db

async def check_rules():
    db = get_mongo_db()
    cursor = db.golden_rules.find({})
    total = 0
    async for doc in cursor:
        rules = doc.get("rules", [])
        total += len(rules)
        print(f"[{doc['_id']}]: {len(rules)} rules")
    print(f"TOTAL: {total}")

if __name__ == "__main__":
    asyncio.run(check_rules())
