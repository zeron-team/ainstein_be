#!/usr/bin/env python3
import asyncio
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.adapters.mongo_client import get_mongo_db

async def migrate():
    db = get_mongo_db()
    print("Starting migration...")
    
    motivo_doc = await db.golden_rules.find_one({"_id": "motivo"})
    if not motivo_doc:
        print("No 'motivo' doc found")
        return
        
    motivo_internacion_doc = await db.golden_rules.find_one({"_id": "motivo_internacion"})
    rules_to_move = motivo_doc.get("rules", [])
    print(f"Moving {len(rules_to_move)} rules from 'motivo' to 'motivo_internacion'")
    
    if not motivo_internacion_doc:
        print("No 'motivo_internacion' found, renaming 'motivo'.")
        await db.golden_rules.update_one(
            {"_id": "motivo"},
            {"$set": {"_id": "motivo_internacion", "title": "Motivo de Internación"}}
        )
    else:
        existing_rules = motivo_internacion_doc.get("rules", [])
        existing_rules.extend(rules_to_move)
        await db.golden_rules.update_one(
            {"_id": "motivo_internacion"},
            {"$set": {"rules": existing_rules, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        await db.golden_rules.delete_one({"_id": "motivo"})
        
    print("Migration finished!")

if __name__ == "__main__":
    asyncio.run(migrate())
