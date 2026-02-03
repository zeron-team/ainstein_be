import asyncio
from app.adapters.mongo_client import db
from app.domain.models import User
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO)

async def check():
    # List all feedbacks to see structure
    feedbacks = await db.epc_feedback.find().to_list(10)
    print(f"Total feedbacks found: {len(feedbacks)}")
    for f in feedbacks:
        print(f"ID: {f.get('_id')}, CreatedBy: {f.get('created_by')} (Type: {type(f.get('created_by'))}), Text: {f.get('feedback_text')}")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(check())
