from __future__ import annotations

from urllib.parse import urlparse
from typing import Iterable, List, Tuple, Optional, Any, Dict

from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorDatabase,
    AsyncIOMotorCollection,
)
from pymongo.errors import OperationFailure

from app.core.config import settings

# Colecciones candidatas donde pueden aterrizar las HCE
HCE_COLLECTIONS_CANDIDATES: List[str] = [
    "hce_docs",          # prioridad 1 (la que usamos en /hce/upload)
    "hce",
    "hce_parsed",
    "hce_docs_parsed",
    "epc_hce",
]

def _database_name_from_url(url: str, default: str = "epc") -> str:
    try:
        parsed = urlparse(url)
        path = (parsed.path or "").lstrip("/")
        return path or (settings.MONGO_DB_NAME or default)
    except Exception:
        return settings.MONGO_DB_NAME or default

_DB_NAME: str = settings.MONGO_DB_NAME or _database_name_from_url(settings.MONGO_URL)

_client = AsyncIOMotorClient(
    settings.MONGO_URL,
    uuidRepresentation="standard",
    serverSelectionTimeoutMS=5000,
    tz_aware=True,
)

db: AsyncIOMotorDatabase = _client[_DB_NAME]

__all__ = [
    "db",
    "get_mongo",
    "get_mongo_db",
    "get_collection",
    "list_existing_collections",
    "pick_hce_collections",
    "ensure_index",
    "ensure_indexes",
    "ping",
    "close",
]

def get_mongo() -> AsyncIOMotorClient:
    return _client

def get_mongo_db() -> AsyncIOMotorDatabase:
    return db

def get_collection(name: str) -> AsyncIOMotorCollection:
    return db[name]

async def list_existing_collections() -> List[str]:
    try:
        return await db.list_collection_names()
    except Exception:
        return []

async def pick_hce_collections() -> List[AsyncIOMotorCollection]:
    return [db[name] for name in HCE_COLLECTIONS_CANDIDATES]

async def ping(timeout_ms: int = 3000) -> bool:
    try:
        await _client.admin.command("ping", maxTimeMS=timeout_ms)
        return True
    except Exception:
        return False

async def close() -> None:
    _client.close()

# ---------- índices ----------
def _as_key_tuple(keys: Iterable[Tuple[str, int | str]]) -> Tuple[Tuple[str, Any], ...]:
    norm: List[Tuple[str, Any]] = []
    for k, v in keys:
        try:
            norm.append((k, int(v)))
        except Exception:
            norm.append((k, v))
    return tuple(norm)

async def _existing_index_keys(coll: AsyncIOMotorCollection) -> Dict[Tuple[Tuple[str, Any], ...], str]:
    by_keys: Dict[Tuple[Tuple[str, Any], ...], str] = {}
    for idx in await coll.list_indexes().to_list(length=None):
        key_pairs = tuple(idx["key"].items())  # type: ignore
        by_keys[key_pairs] = idx.get("name", "")
    return by_keys

async def ensure_index(
    coll: AsyncIOMotorCollection,
    keys: List[Tuple[str, int | str]],
    name: Optional[str] = None,
    **kwargs: Any,
) -> str:
    key_tuple = _as_key_tuple(keys)
    existing = await _existing_index_keys(coll)
    if key_tuple in existing:
        return existing[key_tuple]
    try:
        return await coll.create_index(keys, name=name, **kwargs)
    except OperationFailure as e:
        if getattr(e, "code", None) == 85:
            existing = await _existing_index_keys(coll)
            if key_tuple in existing:
                return existing[key_tuple]
        raise

async def ensure_indexes() -> None:
    # HCEs
    for coll in await pick_hce_collections():
        await ensure_index(coll, [("patient_id", 1), ("created_at", -1)], name="ix_hce_patient_created")
        await ensure_index(coll, [("patient.id", 1), ("created_at", -1)], name="ix_hce_patientdot_created")
        await ensure_index(coll, [("patientId", 1), ("created_at", -1)], name="ix_hce_patientId_created")
        await ensure_index(coll, [("paciente_id", 1), ("created_at", -1)], name="ix_hce_paciente_id_created")
        await ensure_index(coll, [("paciente.id", 1), ("created_at", -1)], name="ix_hce_pacientedot_created")
        await ensure_index(coll, [("admission_id", 1), ("created_at", -1)], name="ix_hce_admission_created")
        await ensure_index(coll, [("admission.id", 1), ("created_at", -1)], name="ix_hce_admissiondot_created")
        await ensure_index(coll, [("admision_id", 1), ("created_at", -1)], name="ix_hce_admision_created")
        await ensure_index(coll, [("dni", 1)], name="ix_hce_dni")
        await ensure_index(coll, [("cuil", 1)], name="ix_hce_cuil")
        await ensure_index(coll, [("patient.dni", 1)], name="ix_hce_patientdot_dni")
        await ensure_index(coll, [("paciente.dni", 1)], name="ix_hce_pacientedot_dni")
        await ensure_index(coll, [("text", "text")], name="ix_hce_text_es", default_language="spanish")
        await ensure_index(coll, [("created_at", -1)], name="ix_hce_created_at")

    # EPC principal
    epc = db["epc_docs"]
    await ensure_index(epc, [("patient_id", 1), ("updated_at", -1)], name="ix_epc_patient_updated")
    await ensure_index(epc, [("admission_id", 1), ("updated_at", -1)], name="ix_epc_admission_updated")
    await ensure_index(epc, [("created_by", 1), ("created_at", -1)], name="ix_epc_createdby_created")
    await ensure_index(epc, [("estado", 1), ("updated_at", -1)], name="ix_epc_estado_updated")
    await ensure_index(epc, [("created_at", -1)], name="ix_epc_created_at")
    await ensure_index(epc, [("updated_at", -1)], name="ix_epc_updated_at")
    await ensure_index(epc, [("hce_origin_id", 1)], name="ix_epc_hce_origin_id")

    # EPC versionado
    ev = db["epc_versions"]
    await ensure_index(ev, [("epc_id", 1), ("generated_at", -1)], name="ix_epcv_epc_generated")
    await ensure_index(ev, [("patient_id", 1), ("generated_at", -1)], name="ix_epcv_patient_generated")
    
    # FERRO D2 v3.0.0: TTL indexes for fire & forget collections
    # Logs - 30 days retention
    epc_logs = db["epc_logs"]
    await ensure_index(epc_logs, [("created_at", 1)], name="ix_epc_logs_ttl", expireAfterSeconds=2592000)
    
    # Chat history - 7 days retention
    chat_history = db["chat_history"]
    await ensure_index(chat_history, [("created_at", 1)], name="ix_chat_history_ttl", expireAfterSeconds=604800)
    
    # LLM usage logs - 90 days retention
    llm_usage = db["llm_usage"]
    await ensure_index(llm_usage, [("timestamp", 1)], name="ix_llm_usage_ttl", expireAfterSeconds=7776000)
    
    # Feedback logs - 60 days retention
    epc_feedback = db["epc_feedback"]
    await ensure_index(epc_feedback, [("created_at", 1)], name="ix_epc_feedback_ttl", expireAfterSeconds=5184000)