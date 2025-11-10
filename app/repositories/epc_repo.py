from sqlalchemy.orm import Session
from app.domain.models import EPC
from bson import ObjectId

class EPCRepo:
    def __init__(self, db: Session, mongo):
        self.db = db
        self.mongo = mongo
        self.versions = mongo["epc_versions"]

    async def upsert_draft(self, patient_id: str, admission_id: str | None, payload: dict, user_id: str) -> EPC:
        import uuid
        epc = self.db.query(EPC).filter(EPC.patient_id == patient_id).first()
        if not epc:
            epc = EPC(id=str(uuid.uuid4()), patient_id=patient_id, admission_id=admission_id,
                      estado='borrador', created_by=user_id)
            self.db.add(epc)
            self.db.commit()
            self.db.refresh(epc)
        doc = {
            "epc_id": epc.id,
            "patient_id": patient_id,
            "status": "draft",
            "payload": payload,
        }
        ins = await self.versions.insert_one(doc)
        epc.version_actual_oid = str(ins.inserted_id)
        epc.estado = 'borrador'
        self.db.commit()
        return epc

    async def get_with_latest_version(self, epc_id: str):
        epc = self.db.query(EPC).get(epc_id)
        if not epc:
            return None, None
        version = None
        if epc.version_actual_oid:
            version = await self.versions.find_one({"_id": ObjectId(epc.version_actual_oid)})
        return epc, version
