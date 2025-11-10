from fastapi import APIRouter, Depends
import uuid
from app.core.deps import get_db, role_required
from app.domain.models import Patient
from app.domain.schemas import PatientIn
from app.repositories.patient_repo import PatientRepo

router = APIRouter(prefix="/patients", tags=["Patients"])

@router.post("")
def create_patient(p: PatientIn, db=Depends(get_db), user=Depends(role_required('medico','admin'))):
    model = Patient(id=str(uuid.uuid4()), apellido=p.apellido, nombre=p.nombre, dni=p.dni, obra_social=p.obra_social, nro_beneficiario=p.nro_beneficiario)
    return PatientRepo(db).create(model)

@router.get("")
def list_patients(estado: str | None = None, db=Depends(get_db), user=Depends(role_required('viewer','medico','admin'))):
    res = PatientRepo(db).list(estado=estado)
    return [{"patient": r[0].__dict__, "status": r[1].__dict__} for r in res]
