# app/routers/debug.py
from __future__ import annotations
from datetime import datetime
from fastapi import APIRouter
from app.adapters.mongo_client import (
    db as mongo,
    list_existing_collections,
    ensure_indexes,
    ping,
)

router = APIRouter(prefix="/debug", tags=["_debug"])

@router.get("/mongo/ping")
async def mongo_ping():
    ok = await ping()
    cols = await list_existing_collections()
    return {
        "ok": ok,
        "db_name": getattr(mongo, "name", None),
        "collections": cols,
    }

@router.post("/mongo/insert-sample")
async def mongo_insert_sample():
    res = await mongo["__samples__"].insert_one({"at": datetime.utcnow()})
    return {"inserted_id": str(res.inserted_id)}

@router.post("/mongo/ensure-indexes")
async def mongo_ensure_indexes():
    await ensure_indexes()
    return {"ok": True}

@router.get("/mongo/stats")
async def mongo_stats():
    cols = await list_existing_collections()
    counts = {}
    for c in cols:
        try:
            counts[c] = await mongo[c].estimated_document_count()
        except Exception:
            counts[c] = None
    return {
        "db_name": getattr(mongo, "name", None),
        "counts": counts,
    }