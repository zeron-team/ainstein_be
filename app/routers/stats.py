from fastapi import APIRouter, Depends
from app.core.deps import get_db, role_required
from app.repositories.kpi_repo import KPIRepo

router = APIRouter(prefix="/stats", tags=["Stats"])

@router.get("/patients/status")
def patients_status(db=Depends(get_db), user=Depends(role_required('viewer','medico','admin'))):
    return KPIRepo(db).patients_by_status()

@router.get("/epc/daily")
def epc_daily(db=Depends(get_db), user=Depends(role_required('viewer','medico','admin'))):
    return KPIRepo(db).epc_daily_current_month()

@router.get("/epc/monthly")
def epc_monthly(db=Depends(get_db), user=Depends(role_required('viewer','medico','admin'))):
    return KPIRepo(db).epc_monthly_current_year()
