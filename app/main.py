from __future__ import annotations

import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.adapters.mongo_client import ensure_indexes, ping
from app.routers import auth, users, patients, admissions, epc, stats, config as cfg, hce

app = FastAPI(title="EPC Suite", version="0.2.0")

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
app.include_router(hce.router)          # <<<<<< IMPORTANTE: montamos HCE
app.include_router(epc.router)
app.include_router(stats.router)
app.include_router(cfg.router)

@app.on_event("startup")
async def _startup():
    # ping + índices en Mongo (idempotente)
    await ping()
    await ensure_indexes()

@app.get("/")
def root():
    return {"ok": True, "service": "EPC Suite"}