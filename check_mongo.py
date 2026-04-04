import asyncio
from app.adapters.mongo_client import get_mongo_db

async def main():
    db = get_mongo_db()
    keys = await db.golden_rules.distinct("_id")
    print("KEYS:", keys)

if __name__ == "__main__":
    asyncio.run(main())
