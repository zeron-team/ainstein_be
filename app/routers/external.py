# app/routers/external.py
"""
External API router for tenant integrations.
Provides REST API endpoints for hospitals/clinics to:
- Request EPC generation
- Retrieve generated EPCs
- Submit patient/HCE data
"""
from __future__ import annotations

import uuid
import logging
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.core.tenant import require_tenant
from app.domain.models import Tenant, Patient, Admission, EPC
from app.adapters.mongo_client import db as mongo

log = logging.getLogger(__name__)

router = APIRouter(prefix="/external", tags=["External API (Tenants)"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class PatientData(BaseModel):
    """Patient data for upsert operations."""
    external_id: str = Field(..., description="External system's patient ID")
    dni: Optional[str] = None
    cuil: Optional[str] = None
    apellido: str
    nombre: str
    fecha_nacimiento: Optional[str] = None
    sexo: Optional[str] = None
    obra_social: Optional[str] = None
    nro_beneficiario: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None


class AdmissionData(BaseModel):
    """Admission data for patient hospitalization."""
    external_id: str = Field(..., description="External system's admission ID")
    patient_external_id: str
    sector: Optional[str] = None
    habitacion: Optional[str] = None
    cama: Optional[str] = None
    fecha_ingreso: datetime
    fecha_egreso: Optional[datetime] = None
    protocolo: Optional[str] = None


class HCEData(BaseModel):
    """Historia Clínica Electrónica data."""
    admission_external_id: str
    text: str = Field(..., description="Full clinical text for EPC generation")
    metadata: Optional[dict] = None


class EPCRequest(BaseModel):
    """Request to generate an EPC."""
    admission_external_id: str
    callback_url: Optional[str] = Field(None, description="URL to POST result when ready")


class EPCResponse(BaseModel):
    """Generated EPC response."""
    id: str
    status: str
    motivo_internacion: Optional[str] = None
    diagnostico_principal_cie10: Optional[str] = None
    evolucion: Optional[str] = None
    procedimientos: Optional[List[str]] = None
    interconsultas: Optional[List[str]] = None
    medicacion: Optional[List[str]] = None
    indicaciones_alta: Optional[List[str]] = None
    recomendaciones: Optional[List[str]] = None
    created_at: Optional[datetime] = None


class TenantInfoResponse(BaseModel):
    """Tenant information response."""
    id: str
    code: str
    name: str
    is_active: bool


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get(
    "/whoami",
    response_model=TenantInfoResponse,
    summary="Get current tenant info from API key",
)
async def whoami(tenant: Tenant = Depends(require_tenant)):
    """Returns information about the tenant associated with the API key."""
    return TenantInfoResponse(
        id=tenant.id,
        code=tenant.code,
        name=tenant.name,
        is_active=tenant.is_active
    )


@router.post(
    "/patients",
    summary="Upsert patient data",
    response_model=dict,
)
async def upsert_patient(
    data: PatientData,
    tenant: Tenant = Depends(require_tenant),
    db: Session = Depends(get_db),
):
    """
    Create or update a patient record.
    The external_id is used to match existing records.
    """
    # Generate internal ID from tenant + external_id for consistency
    internal_id = f"{tenant.code}_{data.external_id}"
    
    existing = db.query(Patient).filter(Patient.id == internal_id).first()
    
    if existing:
        # Update
        for field in ["dni", "cuil", "apellido", "nombre", "fecha_nacimiento", 
                     "sexo", "obra_social", "nro_beneficiario", "telefono", "email"]:
            value = getattr(data, field, None)
            if value is not None:
                setattr(existing, field, value)
        db.commit()
        return {"status": "updated", "patient_id": internal_id}
    else:
        # Create
        patient = Patient(
            id=internal_id,
            tenant_id=tenant.id,
            dni=data.dni,
            cuil=data.cuil,
            apellido=data.apellido,
            nombre=data.nombre,
            fecha_nacimiento=data.fecha_nacimiento,
            sexo=data.sexo,
            obra_social=data.obra_social,
            nro_beneficiario=data.nro_beneficiario,
            telefono=data.telefono,
            email=data.email,
            estado="internacion",
        )
        db.add(patient)
        db.commit()
        return {"status": "created", "patient_id": internal_id}


@router.post(
    "/admissions",
    summary="Upsert admission data",
    response_model=dict,
)
async def upsert_admission(
    data: AdmissionData,
    tenant: Tenant = Depends(require_tenant),
    db: Session = Depends(get_db),
):
    """
    Create or update an admission record.
    """
    internal_id = f"{tenant.code}_{data.external_id}"
    patient_id = f"{tenant.code}_{data.patient_external_id}"
    
    # Verify patient exists
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {data.patient_external_id} not found")
    
    existing = db.query(Admission).filter(Admission.id == internal_id).first()
    
    if existing:
        for field in ["sector", "habitacion", "cama", "fecha_ingreso", "fecha_egreso", "protocolo"]:
            value = getattr(data, field, None)
            if value is not None:
                setattr(existing, field, value)
        db.commit()
        return {"status": "updated", "admission_id": internal_id}
    else:
        admission = Admission(
            id=internal_id,
            patient_id=patient_id,
            tenant_id=tenant.id,
            sector=data.sector,
            habitacion=data.habitacion,
            cama=data.cama,
            fecha_ingreso=data.fecha_ingreso,
            fecha_egreso=data.fecha_egreso,
            protocolo=data.protocolo,
            admision_num=data.external_id,
            estado="internacion",
        )
        db.add(admission)
        db.commit()
        return {"status": "created", "admission_id": internal_id}


@router.post(
    "/hce",
    summary="Submit HCE document for EPC generation",
    response_model=dict,
)
async def submit_hce(
    data: HCEData,
    tenant: Tenant = Depends(require_tenant),
):
    """
    Submit an HCE document which will be used for EPC generation.
    The document is stored in MongoDB.
    """
    admission_id = f"{tenant.code}_{data.admission_external_id}"
    
    hce_doc = {
        "_id": f"hce_{admission_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        "admission_id": admission_id,
        "tenant_id": tenant.id,
        "text": data.text,
        "metadata": data.metadata or {},
        "created_at": datetime.utcnow(),
    }
    
    await mongo.hce_docs.insert_one(hce_doc)
    
    return {"status": "received", "hce_id": hce_doc["_id"]}


@router.post(
    "/epc/request",
    summary="Request EPC generation for an admission",
    response_model=dict,
)
async def request_epc(
    data: EPCRequest,
    background_tasks: BackgroundTasks,
    tenant: Tenant = Depends(require_tenant),
    db: Session = Depends(get_db),
):
    """
    Request generation of an EPC for a specific admission.
    Returns immediately with a job ID; use GET /epc/{id} to retrieve result.
    Optionally provide callback_url for async notification.
    """
    admission_id = f"{tenant.code}_{data.admission_external_id}"
    
    # Verify admission exists
    admission = db.query(Admission).filter(Admission.id == admission_id).first()
    if not admission:
        raise HTTPException(status_code=404, detail=f"Admission {data.admission_external_id} not found")
    
    # Create EPC document in MongoDB (pending state)
    epc_id = str(uuid.uuid4())
    epc_doc = {
        "_id": epc_id,
        "patient_id": admission.patient_id,
        "admission_id": admission_id,
        "tenant_id": tenant.id,
        "estado": "pending",
        "callback_url": data.callback_url,
        "created_at": datetime.utcnow(),
    }
    
    await mongo.epc_docs.insert_one(epc_doc)
    
    # TODO: Add background task to generate EPC
    # background_tasks.add_task(generate_epc_async, epc_id, tenant.id)
    
    return {
        "status": "queued",
        "epc_id": epc_id,
        "message": "EPC generation has been queued. Use GET /external/epc/{id} to check status."
    }


@router.get(
    "/epc/{epc_id}",
    summary="Retrieve generated EPC",
    response_model=EPCResponse,
)
async def get_epc(
    epc_id: str,
    tenant: Tenant = Depends(require_tenant),
):
    """
    Retrieve a generated EPC by ID.
    Only returns EPCs belonging to the authenticated tenant.
    """
    epc_doc = await mongo.epc_docs.find_one({
        "_id": epc_id,
        "tenant_id": tenant.id
    })
    
    if not epc_doc:
        raise HTTPException(status_code=404, detail="EPC not found or access denied")
    
    return EPCResponse(
        id=epc_doc["_id"],
        status=epc_doc.get("estado", "unknown"),
        motivo_internacion=epc_doc.get("motivo_internacion"),
        diagnostico_principal_cie10=epc_doc.get("diagnostico_principal_cie10"),
        evolucion=epc_doc.get("evolucion"),
        procedimientos=epc_doc.get("procedimientos"),
        interconsultas=epc_doc.get("interconsultas"),
        medicacion=epc_doc.get("medicacion"),
        indicaciones_alta=epc_doc.get("indicaciones_alta"),
        recomendaciones=epc_doc.get("recomendaciones"),
        created_at=epc_doc.get("created_at"),
    )


@router.get(
    "/epc",
    summary="List EPCs for tenant",
    response_model=List[EPCResponse],
)
async def list_epcs(
    tenant: Tenant = Depends(require_tenant),
    limit: int = Query(default=20, le=100),
    status: Optional[str] = Query(default=None),
):
    """
    List EPCs belonging to the authenticated tenant.
    """
    query = {"tenant_id": tenant.id}
    if status:
        query["estado"] = status
    
    cursor = mongo.epc_docs.find(query).sort("created_at", -1).limit(limit)
    docs = await cursor.to_list(limit)
    
    return [
        EPCResponse(
            id=doc["_id"],
            status=doc.get("estado", "unknown"),
            motivo_internacion=doc.get("motivo_internacion"),
            diagnostico_principal_cie10=doc.get("diagnostico_principal_cie10"),
            evolucion=doc.get("evolucion"),
            created_at=doc.get("created_at"),
        )
        for doc in docs
    ]
