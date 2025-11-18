# backend/app/routers/stats.py   
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db, role_required
from app.repositories.kpi_repo import KPIRepo

router = APIRouter(tags=["Stats"])

# ---- KPIs ----

@router.get("/kpis")
def get_kpis(db: Session = Depends(get_db), user=Depends(role_required("admin", "medico", "viewer"))):
    return KPIRepo(db).kpis()

# Alias con prefijo 'stats' para el frontend que espere /stats/kpis
@router.get("/stats/kpis")
def get_kpis_alias(db: Session = Depends(get_db), user=Depends(role_required("admin", "medico", "viewer"))):
    return KPIRepo(db).kpis()

# ---- Series ----

@router.get("/series/epc/daily")
def series_epc_daily(db: Session = Depends(get_db), user=Depends(role_required("admin", "medico", "viewer"))):
    return KPIRepo(db).epc_daily_current_month()

@router.get("/stats/series/epc/daily")
def series_epc_daily_alias(db: Session = Depends(get_db), user=Depends(role_required("admin", "medico", "viewer"))):
    return KPIRepo(db).epc_daily_current_month()

@router.get("/series/epc/monthly")
def series_epc_monthly(db: Session = Depends(get_db), user=Depends(role_required("admin", "medico", "viewer"))):
    return KPIRepo(db).epc_monthly_last_12()

@router.get("/stats/series/epc/monthly")
def series_epc_monthly_alias(db: Session = Depends(get_db), user=Depends(role_required("admin", "medico", "viewer"))):
    return KPIRepo(db).epc_monthly_last_12()