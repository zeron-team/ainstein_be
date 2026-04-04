import asyncio
from app.adapters.mongo_client import get_mongo_db

async def remove_hc():
    db = get_mongo_db()
    res = await db.golden_rules.delete_one({"_id": "hardcode"})
    print("Deleted count:", res.deleted_count)

if __name__ == "__main__":
    asyncio.run(remove_hc())
