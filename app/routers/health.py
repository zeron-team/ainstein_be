# backend/app/routers/health.py
"""
Healthcheck endpoint para monitorear estado de todos los servicios.
FERRO Stack: Postgres, Redis, Mongo, Qdrant, Rust.
"""

from __future__ import annotations

import logging
from typing import Any, Dict
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.deps import get_db, get_current_user, get_redis
from app.adapters.mongo_client import db as mongo
from app.core.config import settings
from app.domain.models import User

router = APIRouter(prefix="/admin", tags=["admin"])
log = logging.getLogger(__name__)


async def check_postgres(db: Session) -> Dict[str, Any]:
    """Verifica conexión a PostgreSQL (Relational Core)."""
    try:
        result = db.execute(text("SELECT 1"))
        result.fetchone()
        return {"status": "ok", "message": "Connected"}
    except Exception as e:
        return {"status": "error", "message": str(e)[:100]}


async def check_redis() -> Dict[str, Any]:
    """Verifica conexión a Redis (Dopamine Layer)."""
    try:
        redis_client = await get_redis()
        pong = await redis_client.ping()
        if pong:
            return {"status": "ok", "message": "Connected (PONG)"}
        return {"status": "error", "message": "Ping failed"}
    except Exception as e:
        return {"status": "error", "message": str(e)[:100]}


async def check_rust_core() -> Dict[str, Any]:
    """Verifica motor Rust (ainstein_core)."""
    try:
        import ainstein_core
        # Simple proof of life: chunk a string
        result = ainstein_core.chunk_text("Rust is working", 10)
        return {
            "status": "ok", 
            "message": "Connected/Loaded", 
            "result_sample": result
        }
    except ImportError:
        return {"status": "error", "message": "ainstein_core module not found"}
    except Exception as e:
        return {"status": "error", "message": str(e)[:100]}


async def check_mongodb() -> Dict[str, Any]:
    """Verifica conexión a MongoDB (Flexible Store)."""
    try:
        # Ping al servidor
        await mongo.client.admin.command("ping")
        
        # Contar colecciones como verificación adicional
        collections = await mongo.client[mongo.name].list_collection_names()
        return {
            "status": "ok",
            "message": f"Connected ({len(collections)} collections)",
            "database": mongo.name,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)[:100]}


async def check_gemini() -> Dict[str, Any]:
    """Verifica conexión a Gemini API."""
    try:
        if not settings.GEMINI_API_KEY:
            return {"status": "warning", "message": "API key not configured"}
        
        # Hacer una llamada mínima para verificar
        url = f"{settings.GEMINI_API_HOST}/{settings.GEMINI_API_VERSION}/models"
        params = {"key": settings.GEMINI_API_KEY}
        
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
        
        if resp.status_code == 200:
            data = resp.json()
            model_count = len(data.get("models", []))
            return {
                "status": "ok",
                "message": f"Connected ({model_count} models available)",
                "model": settings.GEMINI_MODEL,
            }
        elif resp.status_code in (401, 403):
            return {"status": "error", "message": "Authentication failed"}
        else:
            return {"status": "warning", "message": f"HTTP {resp.status_code}"}
            
    except httpx.TimeoutException:
        return {"status": "error", "message": "Timeout"}
    except Exception as e:
        return {"status": "error", "message": str(e)[:100]}


async def check_ainstein_ws() -> Dict[str, Any]:
    """Verifica conexión al WebService Ainstein (Markey OCI)."""
    try:
        # ✅ Usar settings en lugar de os.getenv()
        api_url = settings.AINSTEIN_API_URL
        api_key = settings.AINSTEIN_API_KEY
        token = settings.AINSTEIN_TOKEN
        
        if not api_key or not token:
            return {"status": "warning", "message": "API key or token not configured"}
        
        # Solo verificar que el endpoint responde (sin enviar datos reales)
        headers = {"Token": token, "Content-Type": "application/json"}
        
        async with httpx.AsyncClient(timeout=10) as client:
            # Enviar request mínimo para verificar conectividad
            resp = await client.get(api_url, headers=headers)
        
        # Cualquier respuesta indica que el servicio está accesible
        return {
            "status": "ok",
            "message": f"Reachable (HTTP {resp.status_code})",
            "url": api_url[:50] + "..." if len(api_url) > 50 else api_url,
        }
        
    except httpx.TimeoutException:
        return {"status": "error", "message": "Timeout"}
    except httpx.ConnectError:
        return {"status": "error", "message": "Connection refused"}
    except Exception as e:
        return {"status": "error", "message": str(e)[:100]}


async def check_qdrant() -> Dict[str, Any]:
    """Verifica conexión a Qdrant (Vector DB)."""
    try:
        if not settings.QDRANT_ENABLED:
            return {"status": "disabled", "message": "Qdrant not enabled in config"}
        
        from qdrant_client import QdrantClient
        
        client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            timeout=5,
        )
        
        # Listar colecciones como verificación
        collections = client.get_collections()
        count = len(collections.collections)
        
        return {
            "status": "ok",
            "message": f"Connected ({count} collections)",
            "host": f"{settings.QDRANT_HOST}:{settings.QDRANT_PORT}",
        }
        
    except ImportError:
        return {"status": "warning", "message": "qdrant-client not installed"}
    except Exception as e:
        error_msg = str(e)
        if "Connection refused" in error_msg:
            return {"status": "error", "message": "Connection refused (not running?)"}
        return {"status": "error", "message": error_msg[:100]}


async def check_langchain() -> Dict[str, Any]:
    """Verifica disponibilidad de LangChain."""
    try:
        if not settings.RAG_ENABLED:
            return {"status": "disabled", "message": "RAG not enabled in config"}
        
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.prompts import ChatPromptTemplate
        
        return {
            "status": "ok",
            "message": "LangChain available",
            "rag_enabled": settings.RAG_ENABLED,
        }
        
    except ImportError as e:
        return {"status": "warning", "message": f"Missing dependency: {e.name}"}
    except Exception as e:
        return {"status": "error", "message": str(e)[:100]}


async def check_docker() -> Dict[str, Any]:
    """Verifica estado de Docker y containers FERRO."""
    import subprocess
    
    expected_containers = ["ferro_postgres", "ferro_redis", "ferro_mongo", "ferro_qdrant"]
    
    try:
        # Check if Docker daemon is running
        result = subprocess.run(
            ["docker", "info"], 
            capture_output=True, 
            text=True, 
            timeout=5
        )
        
        if result.returncode != 0:
            return {"status": "error", "message": "Docker daemon not running"}
        
        # Get running containers
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}:{{.Status}}"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0:
            return {"status": "error", "message": "Failed to list containers"}
        
        running = {}
        for line in result.stdout.strip().split("\n"):
            if ":" in line:
                name, status = line.split(":", 1)
                running[name] = status
        
        # Check expected containers
        containers_status = []
        all_running = True
        for container in expected_containers:
            if container in running:
                containers_status.append({
                    "name": container,
                    "status": "running",
                    "details": running[container][:30]
                })
            else:
                containers_status.append({
                    "name": container,
                    "status": "stopped",
                    "details": "Not running"
                })
                all_running = False
        
        running_count = sum(1 for c in containers_status if c["status"] == "running")
        
        return {
            "status": "ok" if all_running else ("warning" if running_count > 0 else "error"),
            "message": f"{running_count}/{len(expected_containers)} containers running",
            "containers": containers_status,
            "docker_version": "Available"
        }
        
    except FileNotFoundError:
        return {"status": "disabled", "message": "Docker not installed"}
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": "Docker command timeout"}
    except Exception as e:
        return {"status": "error", "message": str(e)[:100]}


@router.get("/health")
async def get_health_status(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Retorna estado de salud de todos los servicios (FERRO Stack).
    Solo accesible por usuarios autenticados.
    """
    checks = {}
    
    # 0. Docker Containers
    checks["docker"] = await check_docker()
    # 1. Relational Core
    checks["postgres"] = await check_postgres(db)
    # 2. Dopamine Layer
    checks["redis"] = await check_redis()
    # 3. Flexible Store
    checks["mongodb"] = await check_mongodb()
    # 4. Vector Brain
    checks["qdrant"] = await check_qdrant()
    # 5. Rust Engine
    checks["rust_core"] = await check_rust_core()
    
    # External
    checks["gemini_api"] = await check_gemini()
    checks["ainstein_ws"] = await check_ainstein_ws()
    checks["langchain"] = await check_langchain()
    
    # Calcular estado general
    statuses = [c["status"] for c in checks.values()]
    if all(s in ("ok", "disabled") for s in statuses):
        overall = "healthy"
    elif any(s == "error" for s in statuses):
        overall = "unhealthy"
    else:
        overall = "degraded"
    
    return {
        "status": overall,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "services": checks,
        "environment": settings.ENV,
        "stack": "FERRO Dopamine-Polyglot"
    }
