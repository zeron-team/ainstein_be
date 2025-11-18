# app/repositories/hce_repo.py
from typing import Optional, Dict, Any
from app.adapters.mongo_client import db as mongo_db

class HceRepo:
    def __init__(self):
        self.col = mongo_db["hce_docs"]  # sin hardcodear cliente/DB aparte

    async def save_text(self, patient_id: str, text: str, meta: Optional[Dict[str, Any]] = None) -> str:
        doc = {"patient_id": patient_id, "text": text, "meta": meta or {}}
        res = await self.col.insert_one(doc)
        return str(res.inserted_id)