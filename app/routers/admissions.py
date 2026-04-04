# backend/app/routers/admissions.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
import uuid
from datetime import datetime
from app.core.deps import get_db, role_required
from app.domain.models import Admission
from app.repositories.admission_repo import AdmissionRepo

router = APIRouter(prefix="/admissions", tags=["Admissions"])


class AdmissionCreate(BaseModel):
    patient_id: str = Field(..., min_length=1, max_length=200)
    sector: str = Field(default="", max_length=100)
    habitacion: str = Field(default="", max_length=50)
    cama: str = Field(default="", max_length=50)


@router.post("")
def create_admission(
    data: AdmissionCreate,
    db=Depends(get_db),
    user=Depends(role_required("medico", "admin")),
):
    a = Admission(
        id=str(uuid.uuid4()),
        patient_id=data.patient_id,
        sector=data.sector,
        habitacion=data.habitacion,
        cama=data.cama,
        fecha_ingreso=datetime.utcnow(),
    )
    return AdmissionRepo(db).create(a)


@router.get("")
def list_admissions(
    patient_id: str,
    db=Depends(get_db),
    user=Depends(role_required("viewer", "medico", "admin")),
):
    return [x.__dict__ for x in AdmissionRepo(db).list_by_patient(patient_id)]
