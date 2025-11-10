from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.routers import auth, users, patients, admissions, epc, stats, config as cfg, files

app = FastAPI(title="EPC Suite", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router, prefix="/admin", tags=["Users"])
app.include_router(patients.router)
app.include_router(admissions.router)
app.include_router(epc.router)
app.include_router(stats.router)
app.include_router(cfg.router)
app.include_router(files.router)

@app.get("/")
def root():
    return {"ok": True, "service": "EPC Suite"}
