import asyncio
from app.adapters.mongo_client import get_mongo_db

async def count_all_dict():
    db = get_mongo_db()
    count = await db.section_mapping_dictionary.count_documents({})
    print(f"Total dictionary items: {count}")

if __name__ == "__main__":
    asyncio.run(count_all_dict())
