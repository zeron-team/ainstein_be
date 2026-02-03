#!/usr/bin/env python3
"""
Script to migrate Markey configuration from .env to the tenant database.
This enables true multi-tenancy where each tenant has its own config.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.domain.models import Tenant

def migrate_markey_config():
    """Update the Markey tenant with credentials from .env"""
    engine = create_engine(settings.SQL_URL)
    Session = sessionmaker(bind=engine)
    db = Session()
    
    try:
        # Find Markey tenant
        tenant = db.query(Tenant).filter(Tenant.code == "markey").first()
        
        if not tenant:
            print("❌ Tenant 'markey' no encontrado. Ejecuta seed_default_tenant.py primero.")
            return False
        
        print(f"📋 Tenant encontrado: {tenant.name} (ID: {tenant.id})")
        print(f"   Tipo actual: {tenant.integration_type}")
        
        # Update with values from .env
        tenant.integration_type = "inbound"
        tenant.external_endpoint = settings.AINSTEIN_API_URL
        tenant.external_token = settings.AINSTEIN_TOKEN
        tenant.external_auth_type = "bearer"
        
        # Store additional config as JSON in external_headers
        import json
        tenant.external_headers = json.dumps({
            "app": settings.AINSTEIN_APP,
            "api_key": settings.AINSTEIN_API_KEY,
            "http_method": settings.AINSTEIN_HTTP_METHOD,
            "timeout_seconds": settings.AINSTEIN_TIMEOUT_SECONDS,
        })
        
        tenant.notes = f"Migrado desde .env el {__import__('datetime').datetime.now().isoformat()}"
        
        db.commit()
        
        print("\n✅ Configuración migrada exitosamente:")
        print(f"   Endpoint: {tenant.external_endpoint}")
        print(f"   Token: {'*' * 10}...{settings.AINSTEIN_TOKEN[-4:]}")
        print(f"   Auth Type: {tenant.external_auth_type}")
        print(f"   App: {settings.AINSTEIN_APP}")
        print(f"   API Key: {'*' * 10}...{settings.AINSTEIN_API_KEY[-4:]}")
        
        return True
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 60)
    print("🔄 Migrando configuración de Markey a la base de datos...")
    print("=" * 60)
    success = migrate_markey_config()
    sys.exit(0 if success else 1)
