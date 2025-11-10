from fastapi import APIRouter, Depends
import uuid
from datetime import datetime
from app.core.deps import get_db, role_required
from app.domain.models import Admission
from app.repositories.admission_repo import AdmissionRepo

router = APIRouter(prefix="/admissions", tags=["Admissions"])

@router.post("")
def create_admission(patient_id: str, sector: str = "", habitacion: str = "", cama: str = "", db=Depends(get_db), user=Depends(role_required('medico','admin'))):
    a = Admission(id=str(uuid.uuid4()), patient_id=patient_id, sector=sector, habitacion=habitacion, cama=cama, fecha_ingreso=datetime.utcnow())
    return AdmissionRepo(db).create(a)

@router.get("")
def list_admissions(patient_id: str, db=Depends(get_db), user=Depends(role_required('viewer','medico','admin'))):
    return [x.__dict__ for x in AdmissionRepo(db).list_by_patient(patient_id)]
