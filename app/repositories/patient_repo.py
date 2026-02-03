from __future__ import annotations

from typing import List, Optional, Dict
from uuid import uuid4
from datetime import datetime

from sqlalchemy import func, or_, and_
from sqlalchemy.orm import Session

from app.domain.models import Patient, PatientStatus, Admission


class PatientRepo:
    def __init__(self, db: Session):
        self.db = db

    # ---------- CRUD básicos ----------
    def get(self, patient_id: str) -> Optional[Patient]:
        return self.db.get(Patient, patient_id)

    def create(self, payload: Dict) -> Patient:
        row = Patient(
            id=str(uuid4()),
            dni=payload.get("dni"),
            cuil=payload.get("cuil"),
            obra_social=payload.get("obra_social"),
            nro_beneficiario=payload.get("nro_beneficiario"),
            apellido=payload["apellido"],
            nombre=payload["nombre"],
            fecha_nacimiento=payload.get("fecha_nacimiento"),
            sexo=payload.get("sexo"),
            telefono=payload.get("telefono"),
            email=payload.get("email"),
            domicilio=payload.get("domicilio"),
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def update(self, patient_id: str, payload: Dict) -> Optional[Patient]:
        row = self.get(patient_id)
        if not row:
            return None

        # Update fields from payload
        for key, value in payload.items():
            if hasattr(row, key):
                setattr(row, key, value)

        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, patient_id: str) -> bool:
        row = self.get(patient_id)
        if not row:
            return False

        self.db.delete(row)
        self.db.commit()
        return True

    # ---------- Estado del paciente ----------
    def upsert_status(self, patient_id: str, *, estado: str, observaciones: Optional[str]) -> None:
        """
        Estado CANÓNICO en patients.estado.
        Tabla patient_status se mantiene solo por compatibilidad / auditoría.
        """
        # 1) Actualizamos el paciente
        patient = self.db.get(Patient, patient_id)
        if patient:
            patient.estado = estado

        # 2) Actualizamos / insertamos en patient_status
        cur = (
            self.db.query(PatientStatus)
            .filter(PatientStatus.patient_id == patient_id)
            .one_or_none()
        )
        if cur:
            cur.estado = estado
            cur.observaciones = observaciones
        else:
            cur = PatientStatus(
                patient_id=patient_id,
                estado=estado,
                observaciones=observaciones,
            )
            self.db.add(cur)

        self.db.commit()

    def get_status(self, patient_id: str) -> Optional[str]:
        """
        Devuelve primero el estado desde patients.estado.
        Si no hay, cae a patient_status.estado (compatibilidad hacia atrás).
        """
        patient = self.db.get(Patient, patient_id)
        if patient and getattr(patient, "estado", None):
            return patient.estado

        cur = (
            self.db.query(PatientStatus)
            .filter(PatientStatus.patient_id == patient_id)
            .one_or_none()
        )
        return cur.estado if cur else None

    def count_by_estado(self) -> Dict[str, int]:
        """
        Cuenta por estado usando la tabla patients como fuente de verdad.
        """
        base: Dict[str, int] = {
            "internacion": 0,
            "falta_epc": 0,
            "epc_generada": 0,
            "alta": 0,
        }
        rows = (
            self.db.query(Patient.estado, func.count(Patient.id))
            .group_by(Patient.estado)
            .all()
        )
        for est, cnt in rows:
            if not est:
                continue
            if est in base:
                base[est] = int(cnt or 0)
        return base

    # ---------- Listado con búsqueda / paginación ----------
    def list(
        self,
        q: Optional[str] = None,
        estado: Optional[str] = None,
        offset: int = 0,
        limit: int = 50,
    ) -> List[dict]:
        """
        Lista de pacientes para el listado principal.

        - El campo 'estado' que se devuelve sale de patients.estado.
          Si está NULL, se usa patient_status.estado.
        - Filtro 'estado' matchea en ambos campos (para compatibilidad).
        - Además trae info de la última admisión del paciente (admissions):
          admision_num, sector, habitacion, cama.
        - Los datos de EPC (created_by_name, created_at) se enriquecen desde MongoDB en el router.
        """

        # Subquery para obtener la ÚLTIMA admisión por paciente
        sub_last_adm = (
            self.db.query(
                Admission.patient_id.label("patient_id"),
                func.max(Admission.fecha_ingreso).label("max_fecha_ingreso"),
            )
            .group_by(Admission.patient_id)
            .subquery()
        )

        qry = (
            self.db.query(
                Patient,
                PatientStatus.estado.label("status_estado"),
                Admission.admision_num,
                Admission.sector,
                Admission.habitacion,
                Admission.cama,
                Admission.fecha_ingreso,
                Admission.fecha_egreso,
            )
            .outerjoin(PatientStatus, PatientStatus.patient_id == Patient.id)
            # join con la última admisión
            .outerjoin(
                sub_last_adm,
                sub_last_adm.c.patient_id == Patient.id,
            )
            .outerjoin(
                Admission,
                and_(
                    Admission.patient_id == Patient.id,
                    Admission.fecha_ingreso == sub_last_adm.c.max_fecha_ingreso,
                ),
            )
        )

        if q:
            like = f"%{q.lower()}%"
            qry = qry.filter(
                or_(
                    func.lower(Patient.apellido).like(like),
                    func.lower(Patient.nombre).like(like),
                    func.lower(Patient.dni).like(like),
                )
            )

        if estado:
            qry = qry.filter(
                or_(
                    Patient.estado == estado,
                    PatientStatus.estado == estado,
                )
            )

        rows = (
            qry.order_by(Patient.apellido.asc(), Patient.nombre.asc())
            .offset(offset)
            .limit(min(limit, 200))
            .all()
        )

        out: List[dict] = []
        for p, status_estado, adm_num, sector, habitacion, cama, fingreso, fegreso in rows:
            # Calcular edad (simple)
            edad = None
            if p.fecha_nacimiento:
                try:
                    # Intento basico YYYY-MM-DD
                    bd = datetime.strptime(str(p.fecha_nacimiento)[:10], "%Y-%m-%d")
                    now = datetime.utcnow()
                    edad = now.year - bd.year - ((now.month, now.day) < (bd.month, bd.day))
                except:
                    pass

            # Dias estada
            dias_estada = None
            if fingreso:
                end_dt = fegreso or datetime.utcnow()
                dias_estada = (end_dt - fingreso).days

            # prioridad: patients.estado -> patient_status.estado -> 'internacion'
            est_final = p.estado or status_estado or "internacion"
            out.append(
                {
                    "id": p.id,
                    "apellido": p.apellido,
                    "nombre": p.nombre,
                    "dni": p.dni,
                    "obra_social": p.obra_social,
                    "nro_beneficiario": p.nro_beneficiario,
                    # columnas que usa el list.tsx
                    "hce_adm": adm_num,
                    "movimiento_id": adm_num, # Nuevo campo solicitado como "Mov"
                    "sector": sector,
                    "habitacion": habitacion,
                    "cama": cama,
                    "estado": est_final,
                    # Estos campos se enriquecen desde MongoDB en el router
                    "epc_created_by_name": None,
                    "epc_created_at": None,
                    # Nuevos campos solicitados
                    "fecha_ingreso": fingreso.isoformat() if fingreso else None,
                    "fecha_egreso": fegreso.isoformat() if fegreso else None,
                    "edad": edad,
                    "sexo": p.sexo,
                    "dias_estada": dias_estada,
                    "tipo_alta": "-", # No disponible en modelo actual
                }
            )
        return out

    def count(self, q: Optional[str] = None, estado: Optional[str] = None) -> int:
        """
        Cuenta total de pacientes con los mismos filtros que list().
        (No necesita join con Admissions para contar.)
        """
        qry = (
            self.db.query(func.count(Patient.id))
            .outerjoin(PatientStatus, PatientStatus.patient_id == Patient.id)
        )
        if q:
            like = f"%{q.lower()}%"
            qry = qry.filter(
                or_(
                    func.lower(Patient.apellido).like(like),
                    func.lower(Patient.nombre).like(like),
                    func.lower(Patient.dni).like(like),
                )
            )
        if estado:
            qry = qry.filter(
                or_(
                    Patient.estado == estado,
                    PatientStatus.estado == estado,
                )
            )
        return int(qry.scalar() or 0)