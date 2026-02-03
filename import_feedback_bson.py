#!/usr/bin/env python3
"""
Script to import epc_feedback.bson into MongoDB.
Uses the bson library (from pymongo) to parse the BSON file directly.
"""
import asyncio
import bson
import logging
from pathlib import Path
from app.adapters.mongo_client import db as mongo

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

BSON_FILE = Path("/home/ubuntu/ainstein/db_dumps/extracted/mongo_epc/epc_feedback.bson")


async def import_feedback():
    if not BSON_FILE.exists():
        log.error(f"BSON file not found: {BSON_FILE}")
        return

    log.info(f"Reading BSON file: {BSON_FILE}")
    
    # Read all documents from BSON file
    documents = []
    with open(BSON_FILE, "rb") as f:
        data = f.read()
    
    # BSON files from mongodump are concatenated BSON documents
    # We need to decode them one by one
    offset = 0
    while offset < len(data):
        # First 4 bytes are the document size (little-endian int32)
        if offset + 4 > len(data):
            break
        doc_size = int.from_bytes(data[offset:offset+4], 'little')
        if doc_size <= 0 or offset + doc_size > len(data):
            break
        
        doc_data = data[offset:offset+doc_size]
        try:
            doc = bson.BSON(doc_data).decode()
            documents.append(doc)
        except Exception as e:
            log.warning(f"Failed to decode document at offset {offset}: {e}")
        
        offset += doc_size
    
    log.info(f"Parsed {len(documents)} documents from BSON file")
    
    if not documents:
        log.warning("No documents to import!")
        return
    
    # Show sample of what we're importing
    log.info("Sample document structure:")
    sample = documents[0]
    for k, v in sample.items():
        log.info(f"  {k}: {type(v).__name__} = {repr(v)[:100]}")
    
    # Drop existing collection and insert new data
    log.info("Dropping existing epc_feedback collection...")
    await mongo.epc_feedback.drop()
    
    log.info(f"Inserting {len(documents)} documents...")
    result = await mongo.epc_feedback.insert_many(documents)
    log.info(f"Successfully inserted {len(result.inserted_ids)} documents!")
    
    # Verify
    count = await mongo.epc_feedback.count_documents({})
    log.info(f"Verification: Collection now has {count} documents")
    
    # Show some stats
    with_text = await mongo.epc_feedback.count_documents({"feedback_text": {"$ne": None, "$exists": True}})
    log.info(f"  - With feedback_text: {with_text}")
    
    # Count by rating
    for rating in ["ok", "partial", "bad"]:
        cnt = await mongo.epc_feedback.count_documents({"rating": rating})
        log.info(f"  - Rating '{rating}': {cnt}")


if __name__ == "__main__":
    asyncio.run(import_feedback())
