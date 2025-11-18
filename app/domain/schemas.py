# app/domain/schemas.py
from __future__ import annotations

from typing import Optional, List, Literal
from pydantic import BaseModel, Field, ConfigDict

# ---------------------------
# Helpers
# ---------------------------
class Msg(BaseModel):
    message: str

# ---------------------------
# USERS / AUTH
# ---------------------------
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=80)
    full_name: str = Field(..., min_length=1, max_length=120)
    email: Optional[str] = Field(default=None, max_length=120)
    role: Literal["admin", "medico", "viewer"]
    model_config = ConfigDict(from_attributes=True)

class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=128)

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[Literal["admin", "medico", "viewer"]] = None
    is_active: Optional[bool] = None

class UserOut(UserBase):
    id: str
    is_active: bool = True

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

# ---------------------------
# PATIENTS
# ---------------------------
class PatientBase(BaseModel):
    apellido: str = Field(..., min_length=1, max_length=80)
    nombre: str = Field(..., min_length=1, max_length=80)
    dni: Optional[str] = Field(default=None, max_length=20)
    cuil: Optional[str] = Field(default=None, max_length=20)
    obra_social: Optional[str] = Field(default=None, max_length=80)
    nro_beneficiario: Optional[str] = Field(default=None, max_length=50)
    fecha_nacimiento: Optional[str] = Field(default=None, max_length=10)
    sexo: Optional[str] = Field(default=None, max_length=10)
    telefono: Optional[str] = Field(default=None, max_length=40)
    email: Optional[str] = Field(default=None, max_length=120)
    domicilio: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class PatientCreate(PatientBase):
    pass

class PatientUpdate(BaseModel):
    apellido: Optional[str] = None
    nombre: Optional[str] = None
    dni: Optional[str] = None
    cuil: Optional[str] = None
    obra_social: Optional[str] = None
    nro_beneficiario: Optional[str] = None
    fecha_nacimiento: Optional[str] = None
    sexo: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    domicilio: Optional[str] = None

class PatientOut(PatientBase):
    id: str

# ---------------------------
# ADMISSIONS
# ---------------------------
class AdmissionBase(BaseModel):
    patient_id: str
    sector: Optional[str] = None
    habitacion: Optional[str] = None
    cama: Optional[str] = None
    fecha_ingreso: str
    fecha_egreso: Optional[str] = None
    protocolo: Optional[str] = None
    admision_num: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class AdmissionCreate(AdmissionBase):
    pass

class AdmissionOut(AdmissionBase):
    id: str

# ---------------------------
# EPC
# ---------------------------
class EPCGenReq(BaseModel):
    patient_id: str
    admission_id: Optional[str] = None
    hce_text: Optional[str] = None
    extra_instructions: Optional[str] = None

class EPCSectionMedicacion(BaseModel):
    farmaco: str
    dosis: Optional[str] = None
    via: Optional[str] = None
    frecuencia: Optional[str] = None

class EPCUpdate(BaseModel):
    titulo: Optional[str] = None
    diagnostico_principal_cie10: Optional[str] = None
    fecha_emision: Optional[str] = None
    medico_responsable: Optional[str] = None
    firmado_por_medico: Optional[bool] = None
    motivo_internacion: Optional[str] = None
    evolucion: Optional[str] = None
    procedimientos: Optional[List[str]] = None
    interconsultas: Optional[List[str]] = None
    medicacion: Optional[List[EPCSectionMedicacion]] = None
    indicaciones_alta: Optional[List[str]] = None
    recomendaciones: Optional[List[str]] = None

class EPCOut(BaseModel):
    id: Optional[str] = None
    patient_id: str
    admission_id: Optional[str] = None
    estado: Literal["borrador", "validada", "impresa"] = "borrador"
    titulo: Optional[str] = None
    diagnostico_principal_cie10: Optional[str] = None
    fecha_emision: Optional[str] = None
    medico_responsable: Optional[str] = None
    firmado_por_medico: Optional[bool] = None
    motivo_internacion: Optional[str] = None
    evolucion: Optional[str] = None
    procedimientos: Optional[List[str]] = None
    interconsultas: Optional[List[str]] = None
    medicacion: Optional[List[EPCSectionMedicacion]] = None
    indicaciones_alta: Optional[List[str]] = None
    recomendaciones: Optional[List[str]] = None
    model_config = ConfigDict(from_attributes=True)

# ---------------------------
# KPI / Dashboard
# ---------------------------
class KPIItem(BaseModel):
    key: str
    value: int

class KPIsOut(BaseModel):
    items: List[KPIItem] = []

# ---------------------------
# HCE -> Import / Parse
# ---------------------------
class HceImportResponse(BaseModel):
    status: Literal["created", "updated", "error"] = "created"
    patient: Optional[PatientOut] = None
    admission: Optional[AdmissionOut] = None
    hce_text_preview: Optional[str] = None
    pages: Optional[int] = None
    source_filename: Optional[str] = None
    message: Optional[str] = None
    
    
# ---------------------------
# BRANDING / CONFIG
# ---------------------------
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from pydantic import ConfigDict

class BrandingBase(BaseModel):
    hospital_nombre: Optional[str] = None
    logo_url: Optional[str] = None
    header_linea1: Optional[str] = None
    header_linea2: Optional[str] = None
    footer_linea1: Optional[str] = None
    footer_linea2: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class BrandingIn(BrandingBase):
    """Payload de entrada para crear/actualizar branding."""
    pass

class BrandingOut(BrandingBase):
    """Respuesta hacia el frontend."""
    id: int
    updated_at: Optional[datetime] = None