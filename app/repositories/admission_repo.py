from app.domain.models import Admission
from sqlalchemy.orm import Session

class AdmissionRepo:
    def __init__(self, db: Session):
        self.db = db

    def create(self, a: Admission):
        self.db.add(a)
        self.db.commit()
        self.db.refresh(a)
        return a

    def list_by_patient(self, patient_id: str, limit: int = 50):
        return self.db.query(Admission).filter(Admission.patient_id == patient_id).limit(limit).all()
