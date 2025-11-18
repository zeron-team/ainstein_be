# backend/app/routers/config.py
from fastapi import APIRouter, Depends
from app.core.deps import get_db, role_required
from app.repositories.branding_repo import BrandingRepo
from app.domain.schemas import BrandingIn

router = APIRouter(prefix="/config", tags=["Config"])

@router.get("/branding")
def get_branding(db=Depends(get_db), user=Depends(role_required('viewer','medico','admin'))):
    b = BrandingRepo(db).get_active()
    return b.__dict__ if b else {}

@router.put("/branding")
def update_branding(data: BrandingIn, db=Depends(get_db), user=Depends(role_required('admin'))):
    return BrandingRepo(db).update(data.dict(exclude_unset=True)).__dict__
