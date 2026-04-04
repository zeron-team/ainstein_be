import asyncio
from app.adapters.mongo_client import get_mongo_db

async def check_dict():
    db = get_mongo_db()
    cursor = db.section_mapping_dictionary.find({})
    async for doc in cursor:
        print(f"Pattern: {doc.get('item_pattern')} -> Target: {doc.get('target_section')}")

if __name__ == "__main__":
    asyncio.run(check_dict())
