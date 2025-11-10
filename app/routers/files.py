from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
import os, uuid
from app.core.deps import role_required
from app.adapters.mongo_client import db as mongo
from app.services.hce_parser import ensure_upload_dir

router = APIRouter(prefix="/files", tags=["Files"])

@router.post("/hce")
async def upload_hce(patient_id: str, f: UploadFile = File(...), user=Depends(role_required('medico','admin'))):
    upload_dir = ensure_upload_dir()
    ext = os.path.splitext(f.filename)[1].lower()
    fname = f"{uuid.uuid4()}{ext}"
    path = os.path.join(upload_dir, fname)
    with open(path, "wb") as out:
        out.write(await f.read())
    doc = {"patient_id": patient_id, "type": "pdf" if ext==".pdf" else "file", "path": path}
    ins = await mongo["hce_files"].insert_one(doc)
    return {"hce_oid": str(ins.inserted_id), "path": path}
