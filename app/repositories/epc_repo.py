from __future__ import annotations
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, desc
from uuid import uuid4
from app.domain.models import EPC


class EPCRepo:
    def __init__(self, db: Session):
        self.db = db

    # lecturas
    def get(self, epc_id: str) -> Optional[EPC]:
        return self.db.get(EPC, epc_id)

    def get_by_patient_adm(self, patient_id: str, admission_id: Optional[str]) -> Optional[EPC]:
        stmt = select(EPC).where(EPC.patient_id == patient_id)
        if admission_id:
            stmt = stmt.where(EPC.admission_id == admission_id)
        else:
            stmt = stmt.where(EPC.admission_id.is_(None))
        stmt = stmt.order_by(desc(EPC.created_at)).limit(1)
        return self.db.execute(stmt).scalars().first()

    # escrituras
    def create(self, *, patient_id: str, admission_id: Optional[str], created_by: str) -> EPC:
        row = EPC(
            id=str(uuid4()),
            patient_id=patient_id,
            admission_id=admission_id,
            estado="borrador",
            created_by=created_by,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def update(self, epc_id: str, payload: dict) -> Optional[EPC]:
        row = self.get(epc_id)
        if not row:
            return None
        
        for key, value in payload.items():
            if hasattr(row, key):
                setattr(row, key, value)
        
        self.db.commit()
        self.db.refresh(row)
        return row

    def update_generated(self, epc_id: str, *, version_oid: str,
                         titulo: Optional[str], cie10: Optional[str]) -> EPC:
        row = self.get(epc_id)
        assert row, "EPC no encontrada"
        row.version_actual_oid = version_oid
        if titulo is not None:
            row.titulo = titulo
        if cie10 is not None:
            row.diagnostico_principal_cie10 = cie10
        self.db.commit()
        self.db.refresh(row)
        return row