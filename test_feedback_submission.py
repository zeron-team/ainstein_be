import asyncio
from app.adapters.mongo_client import db
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

async def test_insert():
    doc = {
        "epc_id": "test_epc_123",
        "patient_id": "test_pat_456",
        "section": "evolucion",
        "rating": "bad",
        "feedback_text": "Test feedback from script",
        "created_by": "test_user_789",
        "created_at": datetime.utcnow()
    }
    result = await db.epc_feedback.insert_one(doc)
    log.info(f"Inserted document with ID: {result.inserted_id}")

    # Verify insertion
    found = await db.epc_feedback.find_one({"_id": result.inserted_id})
    if found:
        log.info(f"Successfully retrieved document: {found}")
    else:
        log.error("Failed to retrieve inserted document!")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test_insert())
