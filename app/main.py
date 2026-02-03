# backend/app/main.py
from __future__ import annotations

import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.adapters.mongo_client import ensure_indexes, ping

from app.routers import (
    auth,
    users,
    patients,
    admissions,
    epc,
    stats,
    config as cfg,
    hce,
)

from app.routers.ainstein import router as ainstein_router

# ✅ NUEVO: router de ingest
from app.routers.ingest import router as ingest_router

# ✅ NUEVO: router de healthcheck
from app.routers.health import router as health_router

# ✅ NUEVO: router external API (multi-tenant)
from app.routers.external import router as external_router

# ✅ NUEVO: middleware de tenant
from app.core.tenant import TenantContextMiddleware


app = FastAPI(title="EPC Suite", version="3.0.0")  # FERRO D2 v3.0.0

# Middleware de tenant (antes de CORS)
app.add_middleware(TenantContextMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # ya parseado desde .env
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(users.router, prefix="/admin", tags=["Users"])
app.include_router(patients.router)
app.include_router(admissions.router)
app.include_router(hce.router)  # <<<<<< IMPORTANTE: montamos HCE
app.include_router(epc.router)
app.include_router(stats.router)
app.include_router(cfg.router)
app.include_router(ainstein_router)

# ✅ NUEVO: endpoint POST /api/ingest
app.include_router(ingest_router)

# ✅ NUEVO: healthcheck admin
app.include_router(health_router)

# ✅ NUEVO: external API para tenants
app.include_router(external_router, prefix="/api/v1")

# ✅ NUEVO: admin API para gestión de tenants
from app.routers.tenants import router as tenants_router
app.include_router(tenants_router)


@app.on_event("startup")
async def _startup():
    # FERRO D2 v3.0.0: Initialize OpenTelemetry
    from app.core.telemetry import init_telemetry, instrument_fastapi, Metrics
    init_telemetry(service_name="ainstein-api")
    instrument_fastapi(app)
    Metrics.init()
    
    # ping + índices en Mongo (idempotente)
    await ping()
    await ensure_indexes()


@app.get("/")
def root():
    return {"ok": True, "service": "EPC Suite"}