import os
from bson import ObjectId
from pdfminer.high_level import extract_text
from app.core.config import settings

async def extract_text_from_hce(mongo, hce_oid: str | None) -> str:
    if not hce_oid:
        return ""
    hce = await mongo["hce_files"].find_one({"_id": ObjectId(hce_oid)})
    if not hce:
        return ""
    if hce.get("type") == "pdf" and hce.get("path"):
        path = hce.get("path")
        try:
            return extract_text(path)[:80000]
        except Exception:
            return hce.get("text", "")
    return hce.get("text", "")

def ensure_upload_dir():
    os.makedirs(settings.HCE_UPLOAD_DIR, exist_ok=True)
    return settings.HCE_UPLOAD_DIR
