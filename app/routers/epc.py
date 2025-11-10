from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from app.core.deps import get_db, role_required
from app.repositories.epc_repo import EPCRepo
from app.repositories.patient_repo import PatientRepo
from app.repositories.branding_repo import BrandingRepo
from app.adapters.mongo_client import db as mongo
from app.services.epc_service import EPCService
from app.services.pdf_service import render_epc_pdf
from app.domain.schemas import EPCGenReq

router = APIRouter(prefix="/epc", tags=["EPC"])

@router.post("/generate")
async def generate(req: EPCGenReq, db=Depends(get_db), user=Depends(role_required('medico','admin'))):
    svc = EPCService(EPCRepo(db, mongo), PatientRepo(db), mongo, BrandingRepo(db))
    epc = await svc.generate_from_hce(req.patient_id, req.admission_id, req.hce_oid, user["id"])
    return {"epc_id": epc.id, "estado": epc.estado, "version_oid": epc.version_actual_oid}

@router.get("/{epc_id}")
async def get_epc(epc_id: str, db=Depends(get_db), user=Depends(role_required('viewer','medico','admin'))):
    svc = EPCService(EPCRepo(db, mongo), PatientRepo(db), mongo, BrandingRepo(db))
    epc, version = await svc.get_latest(epc_id)
    if not epc:
        raise HTTPException(status_code=404, detail="EPC no encontrada")
    return {"epc": epc.__dict__, "latest_version": version}

@router.post("/{epc_id}/print")
async def print_epc(epc_id: str, db=Depends(get_db), user=Depends(role_required('medico','admin'))):
    svc = EPCService(EPCRepo(db, mongo), PatientRepo(db), mongo, BrandingRepo(db))
    epc, version = await svc.get_latest(epc_id)
    if not epc or not version:
        raise HTTPException(status_code=404, detail="EPC/versión no encontrada")
    pdf = await render_epc_pdf(epc, version.get("payload", {}), BrandingRepo(db).get_active())
    return Response(content=pdf, media_type="application/pdf")
