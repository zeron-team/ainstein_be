# app/domain/models.py
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.dialects.mysql import CHAR, TINYINT
from sqlalchemy.sql import func, text
from sqlalchemy.orm import relationship

from app.db.base import Base


class Role(Base):
    __tablename__ = "roles"

    id = Column(TINYINT, primary_key=True)
    name = Column(String(20), unique=True, nullable=False)


class User(Base):
    __tablename__ = "users"

    id = Column(CHAR(36), primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(120), nullable=False)
    email = Column(String(120), unique=True)
    role_id = Column(TINYINT, ForeignKey("roles.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, onupdate=func.now())

    role = relationship("Role")


class Patient(Base):
    __tablename__ = "patients"

    id = Column(CHAR(36), primary_key=True)
    dni = Column(String(20))
    cuil = Column(String(20))
    obra_social = Column(String(80))
    nro_beneficiario = Column(String(50))
    apellido = Column(String(80), nullable=False)
    nombre = Column(String(80), nullable=False)
    fecha_nacimiento = Column(String(10))
    sexo = Column(String(10))
    # Estado del paciente (internacion / falta_epc / epc_generada / alta / validada, etc.)
    estado = Column(
        String(30),
        nullable=False,
        server_default=text("'internacion'"),
    )
    telefono = Column(String(40))
    email = Column(String(120))
    domicilio = Column(Text)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, onupdate=func.now())


class PatientStatus(Base):
    __tablename__ = "patient_status"

    patient_id = Column(
        CHAR(36),
        ForeignKey("patients.id", ondelete="CASCADE"),
        primary_key=True,
    )
    estado = Column(String(20), nullable=False)
    observaciones = Column(Text)
    updated_at = Column(DateTime, server_default=func.now(), nullable=False)


class Admission(Base):
    __tablename__ = "admissions"

    id = Column(CHAR(36), primary_key=True)
    patient_id = Column(
        CHAR(36),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
    )
    sector = Column(String(120))
    habitacion = Column(String(40))
    cama = Column(String(40))
    fecha_ingreso = Column(DateTime, nullable=False)
    fecha_egreso = Column(DateTime)
    protocolo = Column(String(60))
    admision_num = Column(String(60))
    # Estado de la admisión
    estado = Column(
        String(30),
        nullable=False,
        server_default=text("'internacion'"),
    )


class EPC(Base):
    __tablename__ = "epc"

    id = Column(CHAR(36), primary_key=True)
    patient_id = Column(
        CHAR(36),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
    )
    admission_id = Column(CHAR(36), ForeignKey("admissions.id"))

    # Estado principal
    estado = Column(String(20), nullable=False, default="borrador")

    # Metadatos simples
    version_actual_oid = Column(String(64))
    titulo = Column(String(255))
    diagnostico_principal_cie10 = Column(String(15))
    fecha_emision = Column(DateTime)
    medico_responsable = Column(String(120))
    firmado_por_medico = Column(Boolean, default=False)

    created_by = Column(CHAR(36), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, onupdate=func.now())

    # Contenido editable (opcional en SQL, hoy lo estás manejando en Mongo)
    motivo_internacion = Column(Text)
    evolucion = Column(Text)
    procedimientos = Column(Text)        # líneas separadas por \n
    interconsultas = Column(Text)
    medicacion = Column(Text)
    indicaciones_alta = Column(Text)
    recomendaciones = Column(Text)

    # Auditoría de edición / regeneración
    last_edited_by = Column(CHAR(36), ForeignKey("users.id"))
    last_edited_at = Column(DateTime)
    has_manual_changes = Column(Boolean, default=False)
    regenerated_count = Column(Integer, server_default="0", nullable=False)

    author = relationship("User", foreign_keys=[created_by])
    last_editor = relationship("User", foreign_keys=[last_edited_by])


class EPCEvent(Base):
    """
    Historial de acciones sobre una EPC (creación, generación IA, validación, etc.)
    Se referencia por epc_id (UUID en texto, igual al _id en Mongo).
    No se pone FK a la tabla epc para no acoplarse a que exista siempre el registro en SQL.
    """
    __tablename__ = "epc_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    epc_id = Column(CHAR(36), nullable=False)
    at = Column(DateTime, server_default=func.now(), nullable=False)
    by = Column(String(120))
    action = Column(Text, nullable=False)


class Branding(Base):
    __tablename__ = "branding"

    id = Column(Integer, primary_key=True)
    hospital_nombre = Column(String(160))
    logo_url = Column(String(255))
    header_linea1 = Column(String(255))
    header_linea2 = Column(String(255))
    footer_linea1 = Column(String(255))
    footer_linea2 = Column(String(255))
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )