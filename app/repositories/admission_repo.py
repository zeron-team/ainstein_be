# app/repositories/admission_repo.py
from __future__ import annotations
from typing import Optional, List
from uuid import uuid4
from datetime import datetime
from sqlalchemy.orm import Session

from app.domain.models import Admission

class AdmissionRepo:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        patient_id: str,
        *,
        sector: Optional[str] = None,
        habitacion: Optional[str] = None,
        cama: Optional[str] = None,
        fecha_ingreso: Optional[datetime] = None,
        protocolo: Optional[str] = None,
        admision_num: Optional[str] = None,
    ) -> Admission:
        adm = Admission(
            id=str(uuid4()),
            patient_id=patient_id,
            sector=sector,
            habitacion=habitacion,
            cama=cama,
            fecha_ingreso=fecha_ingreso or datetime.utcnow(),
            protocolo=protocolo,
            admision_num=admision_num,
        )
        self.db.add(adm)
        self.db.commit()
        self.db.refresh(adm)
        return adm

    def get(self, admission_id: str) -> Optional[Admission]:
        return self.db.get(Admission, admission_id)

    def list_by_patient(self, patient_id: str) -> List[Admission]:
        return (
            self.db.query(Admission)
            .filter(Admission.patient_id == patient_id)
            .order_by(Admission.fecha_ingreso.desc())
            .all()
        )