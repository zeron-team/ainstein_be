from app.domain.models import Patient, PatientStatus
from sqlalchemy.orm import Session

class PatientRepo:
    def __init__(self, db: Session):
        self.db = db

    def create(self, p: Patient):
        self.db.add(p)
        ps = PatientStatus(patient_id=p.id, estado='falta_epc')
        self.db.add(ps)
        self.db.commit()
        self.db.refresh(p)
        return p

    def update_estado(self, patient_id: str, estado: str):
        ps = self.db.get(PatientStatus, patient_id)
        if not ps:
            ps = PatientStatus(patient_id=patient_id, estado=estado)
            self.db.add(ps)
        else:
            ps.estado = estado
        self.db.commit()
        return ps

    def list(self, estado: str | None = None, limit: int = 100):
        from app.domain.models import Patient, PatientStatus
        q = self.db.query(Patient, PatientStatus).join(PatientStatus, Patient.id == PatientStatus.patient_id)
        if estado:
            q = q.filter(PatientStatus.estado == estado)
        return q.limit(limit).all()
