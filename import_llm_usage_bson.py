#!/usr/bin/env python3
"""
Script to import llm_usage.bson into MongoDB.
Uses the bson library (from pymongo) to parse the BSON file directly.
"""
import asyncio
import bson
import logging
from pathlib import Path
from app.adapters.mongo_client import db as mongo

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

BSON_FILE = Path("/home/ubuntu/ainstein/db_dumps/extracted/mongo_epc/llm_usage.bson")


async def import_llm_usage():
    if not BSON_FILE.exists():
        log.error(f"BSON file not found: {BSON_FILE}")
        return

    log.info(f"Reading BSON file: {BSON_FILE}")
    
    # Read all documents from BSON file
    documents = []
    with open(BSON_FILE, "rb") as f:
        data = f.read()
    
    # BSON files from mongodump are concatenated BSON documents
    offset = 0
    while offset < len(data):
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
    log.info("Dropping existing llm_usage collection...")
    await mongo.llm_usage.drop()
    
    log.info(f"Inserting {len(documents)} documents...")
    result = await mongo.llm_usage.insert_many(documents)
    log.info(f"Successfully inserted {len(result.inserted_ids)} documents!")
    
    # Verify
    count = await mongo.llm_usage.count_documents({})
    log.info(f"Verification: Collection now has {count} documents")
    
    # Calculate total costs
    pipeline = [
        {"$group": {
            "_id": None,
            "total_input_tokens": {"$sum": "$input_tokens"},
            "total_output_tokens": {"$sum": "$output_tokens"},
            "total_cost_usd": {"$sum": "$cost_usd"}
        }}
    ]
    cursor = mongo.llm_usage.aggregate(pipeline)
    totals = await cursor.to_list(1)
    if totals:
        t = totals[0]
        log.info(f"  - Total input tokens: {t.get('total_input_tokens', 0):,}")
        log.info(f"  - Total output tokens: {t.get('total_output_tokens', 0):,}")
        log.info(f"  - Total cost USD: ${t.get('total_cost_usd', 0):.4f}")


if __name__ == "__main__":
    asyncio.run(import_llm_usage())
