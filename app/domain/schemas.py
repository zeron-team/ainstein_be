from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Any

class UserOut(BaseModel):
    id: str
    username: str
    full_name: str
    email: Optional[EmailStr] = None
    role: str

class UserCreate(BaseModel):
    username: str
    password: str
    full_name: str
    email: Optional[EmailStr] = None
    role_id: int = 2  # medico por defecto

class PatientIn(BaseModel):
    apellido: str
    nombre: str
    dni: Optional[str] = None
    obra_social: Optional[str] = None
    nro_beneficiario: Optional[str] = None

class BrandingIn(BaseModel):
    hospital_nombre: Optional[str] = None
    logo_url: Optional[str] = None
    header_linea1: Optional[str] = None
    header_linea2: Optional[str] = None
    footer_linea1: Optional[str] = None
    footer_linea2: Optional[str] = None

class EPCGenReq(BaseModel):
    patient_id: str
    admission_id: Optional[str] = None
    hce_oid: Optional[str] = None

class EPCVersion(BaseModel):
    payload: Any
    status: str = "draft"
