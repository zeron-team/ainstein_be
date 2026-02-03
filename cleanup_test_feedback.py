import asyncio
from app.adapters.mongo_client import db
import logging

logging.basicConfig(level=logging.INFO)

async def cleanup():
    result = await db.epc_feedback.delete_many({"epc_id": "test_epc_123"})
    print(f"Deleted {result.deleted_count} test records.")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(cleanup())
