#!/usr/bin/env python3
import asyncio
import sys
import os
from bson import ObjectId

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.adapters.mongo_client import get_mongo_db

async def migrate():
    db = get_mongo_db()
    print("Starting backfill migration for from_sections in section_mapping_dictionary...")
    
    # Mapeo por defecto de null a empty array si no existe
    cursor = db.section_mapping_dictionary.find({})
    
    total_docs = 0
    updated_docs = 0
    
    async for doc in cursor:
        total_docs += 1
        source_corrections = doc.get("source_corrections", [])
        
        from_sections = set()
        
        for corr_id in source_corrections:
            try:
                # correction_id in audit log is string, but ObjectId in db
                obj_id = corr_id if isinstance(corr_id, ObjectId) else ObjectId(str(corr_id))
            except:
                continue
                
            corr = await db.epc_section_corrections.find_one({"_id": obj_id})
            if corr:
                print(f"DEBUG Correction {obj_id}: {corr}")
                if corr.get("from_section"):
                    from_sections.add(corr["from_section"])
                
        # Even if empty, set it so we don't process it again (or just to normalize schema)
        await db.section_mapping_dictionary.update_one(
            {"_id": doc["_id"]},
            {"$set": {"from_sections": list(from_sections)}}
        )
        if len(from_sections) > 0:
            updated_docs += 1
            
    print(f"Migration finished. Processed {total_docs} docs, found from_sections for {updated_docs} docs.")

if __name__ == "__main__":
    asyncio.run(migrate())
