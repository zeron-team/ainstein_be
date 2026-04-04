import asyncio
from app.adapters.mongo_client import get_mongo_db

async def count_dict():
    db = get_mongo_db()
    count = await db.section_mapping_dictionary.count_documents({"target_section": "interconsultas"})
    print(f"Dictionary items targeting interconsultas: {count}")
    
    async for doc in db.section_mapping_dictionary.find({"target_section": "interconsultas"}):
        print(f" - {doc.get('item_pattern')}")

if __name__ == "__main__":
    asyncio.run(count_dict())
