#!/usr/bin/env python3
"""
Script to seed the default Markey tenant and assign existing data to it.
"""
import uuid
import asyncio
import logging
from datetime import datetime

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.domain.models import Tenant, User, Patient, Admission, EPC, Branding
from app.core.tenant import generate_api_key, hash_api_key
from app.domain.models import TenantAPIKey

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"
DEFAULT_TENANT_CODE = "markey"
DEFAULT_TENANT_NAME = "Markey OCI"


def seed_default_tenant():
    db: Session = SessionLocal()
    
    try:
        # Check if default tenant exists
        existing = db.query(Tenant).filter(Tenant.id == DEFAULT_TENANT_ID).first()
        
        if existing:
            log.info(f"Default tenant '{DEFAULT_TENANT_CODE}' already exists.")
        else:
            # Create default tenant
            tenant = Tenant(
                id=DEFAULT_TENANT_ID,
                code=DEFAULT_TENANT_CODE,
                name=DEFAULT_TENANT_NAME,
                is_active=True,
                contact_email="admin@markeyoci.com.ar",
                created_at=datetime.utcnow(),
            )
            db.add(tenant)
            db.commit()
            log.info(f"Created default tenant: {DEFAULT_TENANT_NAME} (id={DEFAULT_TENANT_ID})")
        
        # Generate API key for the default tenant
        existing_key = db.query(TenantAPIKey).filter(
            TenantAPIKey.tenant_id == DEFAULT_TENANT_ID
        ).first()
        
        if existing_key:
            log.info(f"Default tenant already has an API key (prefix: {existing_key.key_prefix}...)")
        else:
            full_key, key_hash = generate_api_key(prefix="ak_markey_")
            api_key = TenantAPIKey(
                id=str(uuid.uuid4()),
                tenant_id=DEFAULT_TENANT_ID,
                key_hash=key_hash,
                key_prefix=full_key[:12],
                name="Default Production Key",
                is_active=True,
                created_at=datetime.utcnow(),
            )
            db.add(api_key)
            db.commit()
            log.info(f"Generated API key for default tenant. SAVE THIS KEY (shown only once!):")
            log.info(f"  🔑 API KEY: {full_key}")
        
        # Assign existing records to default tenant
        log.info("Assigning existing records to default tenant...")
        
        # Users
        users_updated = db.query(User).filter(User.tenant_id == None).update(
            {"tenant_id": DEFAULT_TENANT_ID}, synchronize_session=False
        )
        log.info(f"  - Users: {users_updated} assigned")
        
        # Patients
        patients_updated = db.query(Patient).filter(Patient.tenant_id == None).update(
            {"tenant_id": DEFAULT_TENANT_ID}, synchronize_session=False
        )
        log.info(f"  - Patients: {patients_updated} assigned")
        
        # Admissions
        admissions_updated = db.query(Admission).filter(Admission.tenant_id == None).update(
            {"tenant_id": DEFAULT_TENANT_ID}, synchronize_session=False
        )
        log.info(f"  - Admissions: {admissions_updated} assigned")
        
        # EPCs
        epcs_updated = db.query(EPC).filter(EPC.tenant_id == None).update(
            {"tenant_id": DEFAULT_TENANT_ID}, synchronize_session=False
        )
        log.info(f"  - EPCs: {epcs_updated} assigned")
        
        # Branding
        branding_updated = db.query(Branding).filter(Branding.tenant_id == None).update(
            {"tenant_id": DEFAULT_TENANT_ID}, synchronize_session=False
        )
        log.info(f"  - Branding: {branding_updated} assigned")
        
        db.commit()
        log.info("✅ Migration complete!")
        
    except Exception as e:
        db.rollback()
        log.error(f"Error during migration: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_default_tenant()
