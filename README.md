# 🏥 AInstein Backend - FERRO D2 v3.0.0

> Sistema enterprise de backend para generación inteligente de Epicrisis Clínicas con IA.

[![Version](https://img.shields.io/badge/version-3.0.0-blue.svg)](https://github.com/zeron-team/ainstein_be)
[![Python](https://img.shields.io/badge/python-3.11+-green.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-teal.svg)](https://fastapi.tiangolo.com)
[![FERRO](https://img.shields.io/badge/FERRO-D2_v3.0.0-orange.svg)](#arquitectura-ferro-d2)

---

## 📋 Tabla de Contenidos

1. [Arquitectura FERRO D2](#-arquitectura-ferro-d2)
2. [Requisitos del Sistema](#-requisitos-del-sistema)
3. [Instalación Paso a Paso](#-instalación-paso-a-paso)
4. [Estructura del Proyecto](#-estructura-del-proyecto)
5. [Configuración de Variables](#-configuración-de-variables)
6. [Diagramas del Sistema](#-diagramas-del-sistema)
7. [API Endpoints](#-api-endpoints)
8. [Multi-Tenancy](#-multi-tenancy)
9. [Verificación del Sistema](#-verificación-del-sistema)
10. [Comandos Útiles](#-comandos-útiles)
11. [Troubleshooting](#-troubleshooting)

---

## 🏗️ Arquitectura FERRO D2

AInstein Backend implementa la arquitectura **FERRO D2 v3.0.0** (Enterprise Cognitive Systems):

```
┌─────────────────────────────────────────────────────────────────────┐
│                      FERRO D2 v3.0.0 Stack                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌───────────────────┐  ┌───────────────────┐  ┌───────────────┐  │
│   │   🐍 Python       │  │   🦀 Rust Engine  │  │  🤖 Gemini    │  │
│   │   (Orchestrator)  │  │   (ainstein_core) │  │  (LLM API)    │  │
│   └─────────┬─────────┘  └─────────┬─────────┘  └───────┬───────┘  │
│             │                      │                    │          │
│             └──────────────────────┼────────────────────┘          │
│                                    ▼                               │
│   ┌─────────────────────────────────────────────────────────────┐  │
│   │                    D2 Data Layer (Polyglot)                 │  │
│   ├─────────────┬─────────────┬─────────────┬───────────────────┤  │
│   │ 🐘 Postgres │ 🔴 Redis    │ 🍃 MongoDB  │ 🔷 Qdrant         │  │
│   │ (ACID/RLS)  │ (Ephemeral) │ (Flexible)  │ (Vector)          │  │
│   │ Truth Core  │ Cache/Rate  │ HCE/Logs    │ RAG/Embeddings    │  │
│   └─────────────┴─────────────┴─────────────┴───────────────────┘  │
│                                                                     │
│   Features: ABAC ✓ | RLS ✓ | SSE Streaming ✓ | OpenTelemetry ✓    │
└─────────────────────────────────────────────────────────────────────┘
```

### Componentes Clave

| Componente | Tecnología | Propósito |
|------------|------------|-----------|
| **Orchestrator** | Python 3.11+ / FastAPI | Coordinación, API REST, lógica de negocio |
| **Engine** | Rust (ainstein_core) | Chunking de texto, procesamiento de alta velocidad |
| **Truth Core** | PostgreSQL 16 + RLS | Datos ACID, multi-tenancy nativo |
| **Ephemeral Layer** | Redis 7 | Cache, sesiones, rate limiting |
| **Flexible Store** | MongoDB 7 | HCE raw data, feedback, logs |
| **Vector Brain** | Qdrant | RAG, embeddings, few-shot learning |
| **LLM Provider** | Google Gemini 2.0 | Generación de epicrisis con IA |

---

## 💻 Requisitos del Sistema

### Software Requerido

| Requisito | Versión Mínima | Verificar con |
|-----------|----------------|---------------|
| **Ubuntu/Debian** | 22.04+ | `lsb_release -a` |
| **Python** | 3.11+ | `python3 --version` |
| **Docker** | 24.0+ | `docker --version` |
| **Docker Compose** | 2.20+ | `docker compose version` |
| **Rust** | 1.70+ (para compilar engine) | `rustc --version` |
| **Git** | 2.30+ | `git --version` |

### Hardware Mínimo (Producción)

| Recurso | Mínimo | Recomendado |
|---------|--------|-------------|
| **RAM** | 8 GB | 16 GB |
| **CPU** | 2 cores | 4+ cores |
| **Disco** | 50 GB SSD | 100+ GB SSD |

---

## 🚀 Instalación Paso a Paso

### Paso 1: Clonar el Repositorio

```bash
cd ~
git clone https://github.com/zeron-team/ainstein_be.git
cd ainstein_be
```

### Paso 2: Instalar Docker (si no está instalado)

```bash
# Instalar Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker

# Verificar
docker --version
docker compose version
```

### Paso 3: Levantar Infraestructura FERRO (Docker)

```bash
# Crear archivo de secrets
cat > .env.docker << 'EOF'
POSTGRES_PASSWORD=ainstein_secure_2026
MONGO_ROOT_PASSWORD=mongo_secure_2026
EOF

# Levantar containers FERRO D2
docker compose -f docker-compose.prod.yml up -d ferro_postgres ferro_redis ferro_mongo ferro_qdrant

# Verificar que están corriendo
docker ps
```

> **Nota**: Si usas los containers locales de desarrollo, los puertos son:
> - PostgreSQL: `localhost:5432`
> - Redis: `localhost:6379`
> - MongoDB: `localhost:27017`
> - Qdrant: `localhost:6333`

### Paso 4: Crear Entorno Virtual Python

```bash
python3 -m venv .venv
source .venv/bin/activate

# Actualizar pip
pip install --upgrade pip wheel setuptools
```

### Paso 5: Instalar Dependencias Python

```bash
pip install -r requirements.txt
```

### Paso 6: Compilar Motor Rust (ainstein_core)

```bash
# Instalar Rust si no está instalado
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env

# Instalar maturin
pip install maturin

# Compilar el módulo Rust
cd rust_lib
maturin develop --release
cd ..

# Verificar instalación
python -c "import ainstein_core; print('✅ Rust engine OK')"
```

### Paso 7: Configurar Variables de Entorno

```bash
# Crear archivo .env
cat > .env << 'EOF'
# ═══════════════════════════════════════════════════════════════════
# FERRO D2 v3.0.0 - Configuration
# ═══════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────
# PostgreSQL (Truth Core - ACID + RLS)
# ─────────────────────────────────────────────────────────────────
SQL_URL=postgresql://ainstein:ainstein_secure_2026@localhost:5432/ainstein

# ─────────────────────────────────────────────────────────────────
# MongoDB (Flexible Store - HCE/Feedback/Logs)
# ─────────────────────────────────────────────────────────────────
MONGO_URL=mongodb://admin:mongo_secure_2026@localhost:27017/ainstein?authSource=admin
MONGO_DB_NAME=ainstein

# ─────────────────────────────────────────────────────────────────
# Redis (Ephemeral Layer - Cache/Sessions)
# ─────────────────────────────────────────────────────────────────
REDIS_URL=redis://localhost:6379/0

# ─────────────────────────────────────────────────────────────────
# Qdrant (Vector Brain - RAG/Embeddings)
# ─────────────────────────────────────────────────────────────────
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_ENABLED=true

# ─────────────────────────────────────────────────────────────────
# RAG Configuration
# ─────────────────────────────────────────────────────────────────
RAG_ENABLED=true
RAG_FEW_SHOT_EXAMPLES=3

# ─────────────────────────────────────────────────────────────────
# JWT Security
# ─────────────────────────────────────────────────────────────────
JWT_SECRET=tu_clave_jwt_muy_segura_minimo_32_caracteres_aqui
JWT_EXPIRE_MINUTES=60

# ─────────────────────────────────────────────────────────────────
# Google Gemini API (LLM Provider)
# ─────────────────────────────────────────────────────────────────
GEMINI_API_KEY=tu_api_key_de_google_gemini
GEMINI_MODEL=gemini-2.0-flash
GEMINI_API_HOST=https://generativelanguage.googleapis.com
GEMINI_API_VERSION=v1beta

# ─────────────────────────────────────────────────────────────────
# HCE WebService External (Markey Integration)
# Variables por defecto - se migran al tenant después
# ─────────────────────────────────────────────────────────────────
AINSTEIN_API_URL=https://ainstein1.markeyoci.com.ar/obtener
AINSTEIN_APP=AInstein
AINSTEIN_API_KEY=tu_api_key_markey
AINSTEIN_TOKEN=tu_token_markey
AINSTEIN_HTTP_METHOD=GET
AINSTEIN_TIMEOUT_SECONDS=60

# ─────────────────────────────────────────────────────────────────
# CORS & Environment
# ─────────────────────────────────────────────────────────────────
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
ENV=dev
EOF
```

### Paso 8: Ejecutar Migraciones de Base de Datos

```bash
# Activar entorno virtual si no está activo
source .venv/bin/activate

# Ejecutar migraciones Alembic
PYTHONPATH=. alembic upgrade head

# Verificar estado
PYTHONPATH=. alembic current
```

### Paso 9: Crear Tenant y Usuario Admin

```bash
# Crear tenant por defecto (markey)
PYTHONPATH=. python scripts/seed_default_tenant.py

# Migrar configuración HCE al tenant
PYTHONPATH=. python scripts/migrate_markey_to_tenant.py

# Crear usuario administrador
PYTHONPATH=. python create_admin_user.py
```

### Paso 10: Iniciar el Servidor

**Desarrollo:**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Producción (con Gunicorn):**
```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

### Paso 11: Verificar Instalación

```bash
# Verificar endpoint raíz
curl http://localhost:8000/

# Debería responder:
# {"ok": true, "service": "EPC Suite"}
```

Para verificación completa, ver sección [Verificación del Sistema](#-verificación-del-sistema).

---

## 📁 Estructura del Proyecto

```
ainstein_be/
├── 📄 .env                          # Variables de entorno (NO commitear)
├── 📄 .gitignore
├── 📄 alembic.ini                   # Configuración Alembic
├── 📄 requirements.txt              # Dependencias Python
├── 📄 docker-compose.prod.yml       # FERRO D2 Stack
├── 📄 create_admin_user.py          # Script crear admin
├── 📄 README.md                     # Esta documentación
│
├── 📁 app/                          # ═══ APLICACIÓN PRINCIPAL ═══
│   ├── 📄 main.py                   # Punto de entrada FastAPI
│   ├── 📄 __init__.py
│   │
│   ├── 📁 adapters/                 # Adaptadores externos
│   │   └── 📄 mongo_client.py       # Cliente MongoDB async
│   │
│   ├── 📁 core/                     # ═══ NÚCLEO DEL SISTEMA ═══
│   │   ├── 📄 config.py             # Settings (pydantic-settings)
│   │   ├── 📄 deps.py               # Dependencias FastAPI (DB, auth)
│   │   ├── 📄 security.py           # JWT, password hashing
│   │   ├── 📄 abac.py               # 🆕 ABAC Authorization
│   │   ├── 📄 tenant.py             # 🆕 Tenant middleware
│   │   ├── 📄 tenant_context.py     # 🆕 Tenant context vars
│   │   ├── 📄 redis.py              # 🆕 Redis base client
│   │   ├── 📄 redis_client.py       # 🆕 Redis extended client
│   │   ├── 📄 telemetry.py          # 🆕 OpenTelemetry tracing
│   │   └── 📄 pii_filter.py         # 🆕 PII filtering
│   │
│   ├── 📁 db/                       # Base de datos
│   │   ├── 📄 base.py               # Declarative Base SQLAlchemy
│   │   ├── 📄 session.py            # Session factory
│   │   └── 📁 migrations/           # Alembic migrations
│   │       ├── 📄 env.py
│   │       ├── 📄 script.py.mako
│   │       └── 📁 versions/         # Migration files
│   │           ├── 📄 b326df34e12a_initial_postgres_schema.py
│   │           ├── 📄 82c4908f8ccc_add_multitenancy_tables.py
│   │           ├── 📄 a8f4008b2bf0_expand_tenant_integration_options.py
│   │           ├── 📄 c3f0d2v300_rls_multitenant.py
│   │           └── 📄 c3f0d2v301_abac_policies.py
│   │
│   ├── 📁 domain/                   # Modelos del dominio
│   │   ├── 📄 models.py             # Modelos SQLAlchemy (Tenant, User, Patient, etc.)
│   │   ├── 📄 schemas.py            # Schemas Pydantic
│   │   ├── 📄 enums.py              # Enumeraciones
│   │   └── 📁 interfaces/           # Interfaces abstractas
│   │
│   ├── 📁 repositories/             # Capa de acceso a datos
│   │   ├── 📄 patient_repo.py
│   │   ├── 📄 admission_repo.py
│   │   ├── 📄 epc_repo.py
│   │   ├── 📄 hce_repo.py
│   │   ├── 📄 user_repo.py
│   │   ├── 📄 branding_repo.py
│   │   └── 📄 kpi_repo.py
│   │
│   ├── 📁 routers/                  # ═══ ENDPOINTS API ═══
│   │   ├── 📄 auth.py               # POST /auth/login, /auth/logout
│   │   ├── 📄 users.py              # /admin/users CRUD
│   │   ├── 📄 patients.py           # /patients CRUD
│   │   ├── 📄 admissions.py         # /admissions CRUD
│   │   ├── 📄 epc.py                # /epc (generación epicrisis)
│   │   ├── 📄 hce.py                # /hce (historia clínica)
│   │   ├── 📄 ainstein.py           # /ainstein (WS externo multi-tenant)
│   │   ├── 📄 health.py             # /admin/health (healthcheck)
│   │   ├── 📄 tenants.py            # 🆕 /admin/tenants CRUD
│   │   ├── 📄 external.py           # 🆕 /api/v1/external (API para tenants)
│   │   ├── 📄 stats.py              # /stats (KPIs)
│   │   ├── 📄 config.py             # /config (branding)
│   │   ├── 📄 ingest.py             # /ingest (carga datos)
│   │   ├── 📄 files.py              # /files (PDF download)
│   │   └── 📄 debug.py              # /debug (solo desarrollo)
│   │
│   ├── 📁 services/                 # ═══ LÓGICA DE NEGOCIO ═══
│   │   │
│   │   │   # ─── AI/LLM Services ───
│   │   ├── 📄 ai_gemini_service.py        # Gemini API básica
│   │   ├── 📄 ai_langchain_service.py     # LangChain + RAG avanzado
│   │   │
│   │   │   # ─── EPC Generation ───
│   │   ├── 📄 epc_service.py              # Servicio principal EPC
│   │   ├── 📄 epc_orchestrator.py         # 🆕 Orquestador de generación
│   │   ├── 📄 epc_section_generator.py    # 🆕 Generación por secciones
│   │   ├── 📄 epc_pre_validator.py        # 🆕 Pre-validación datos
│   │   ├── 📄 epc_prompts.py              # Prompts para LLM
│   │   ├── 📄 epc_prompts_v2.py           # Prompts v2 optimizados
│   │   ├── 📄 epc_history.py              # Historial de versiones
│   │   ├── 📁 epc/                        # 🆕 Submódulo EPC
│   │   │   ├── 📄 hce_extractor.py        # Extractor de HCE
│   │   │   └── 📄 __init__.py
│   │   │
│   │   │   # ─── HCE Parsing ───
│   │   ├── 📄 hce_parser.py               # Parser básico HCE
│   │   ├── 📄 hce_json_parser.py          # 🆕 Parser JSON estructurado
│   │   ├── 📄 hce_ainstein_parser.py      # 🆕 Parser específico Markey
│   │   │
│   │   │   # ─── Feedback & Analytics ───
│   │   ├── 📄 feedback_insights_service.py # Análisis de feedback
│   │   ├── 📄 feedback_llm_analyzer.py     # LLM análisis de feedback
│   │   ├── 📄 llm_usage_tracker.py         # Tracking costos LLM
│   │   │
│   │   │   # ─── RAG & Vectors ───
│   │   ├── 📄 rag_service.py              # RAG principal
│   │   ├── 📄 vector_service.py           # Vector operations
│   │   ├── 📄 vector_store.py             # Qdrant store
│   │   ├── 📁 vector/                     # Submódulo vectores
│   │   │
│   │   │   # ─── Infrastructure ───
│   │   ├── 📄 redis_cache.py              # 🆕 Redis caching
│   │   ├── 📄 rust_engine.py              # 🆕 Rust FFI wrapper
│   │   │
│   │   │   # ─── Other Services ───
│   │   ├── 📄 patient_service.py
│   │   ├── 📄 pdf_service.py
│   │   └── 📄 ingest_service.py
│   │
│   ├── 📁 utils/                    # Utilidades
│   │   ├── 📄 epc_pdf.py            # Templates PDF
│   │   └── 📄 normalize_ws_payload.py
│   │
│   ├── 📁 rules/                    # 🆕 Reglas de negocio
│   │   └── 📄 __init__.py
│   │
│   ├── 📁 scripts/                  # Scripts internos
│   │   └── 📄 bootstrap_admin.py
│   │
│   ├── 📁 static/                   # Archivos estáticos
│   └── 📁 templates/                # Templates HTML
│
├── 📁 scripts/                      # ═══ SCRIPTS DE SISTEMA ═══
│   ├── 📄 seed_default_tenant.py    # Crear tenant por defecto
│   ├── 📄 migrate_markey_to_tenant.py # Migrar config HCE
│   ├── 📄 restore_from_dump.py      # Restaurar desde backup
│   └── 📄 migrate_mysql_postgres.py # Migración legacy
│
├── 📁 rust_lib/                     # ═══ MOTOR RUST ═══
│   ├── 📄 Cargo.toml                # Dependencias Rust
│   ├── 📄 pyproject.toml            # Config maturin
│   └── 📁 src/
│       └── 📄 lib.rs                # Código Rust (chunk_text, etc.)
│
├── 📁 ferro_engine/                 # 🆕 Engine adicional FERRO
│
├── 📁 docs/                         # Documentación
│   ├── 📄 CHECKLIST_SISTEMA.md      # Checklist de verificación
│   └── 📄 REGLAS_GENERACION_EPC.md  # Reglas de negocio EPC
│
├── 📁 hce/                          # Archivos HCE ejemplo
│
└── 📁 dumps_20260128/               # Backups de datos
```

---

## ⚙️ Configuración de Variables

### Variables Requeridas

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `SQL_URL` | URL PostgreSQL | `postgresql://user:pass@host:5432/db` |
| `MONGO_URL` | URL MongoDB | `mongodb://user:pass@host:27017/db?authSource=admin` |
| `REDIS_URL` | URL Redis | `redis://localhost:6379/0` |
| `JWT_SECRET` | Secreto JWT (32+ chars) | `clave_muy_segura_32_caracteres` |
| `GEMINI_API_KEY` | API Key Google AI | `AIza...` |

### Variables Opcionales

| Variable | Default | Descripción |
|----------|---------|-------------|
| `QDRANT_HOST` | `localhost` | Host Qdrant |
| `QDRANT_PORT` | `6333` | Puerto Qdrant |
| `QDRANT_ENABLED` | `true` | Habilitar Qdrant |
| `RAG_ENABLED` | `true` | Habilitar RAG |
| `RAG_FEW_SHOT_EXAMPLES` | `3` | Ejemplos few-shot |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Modelo Gemini |
| `JWT_EXPIRE_MINUTES` | `60` | Expiración JWT |
| `ENV` | `dev` | Entorno (dev/prod) |

---

## 📊 Diagramas del Sistema

### Flujo de Generación de EPC

```mermaid
sequenceDiagram
    participant U as 👤 Usuario
    participant FE as 🖥️ Frontend
    participant API as ⚙️ FastAPI
    participant ORC as 🎯 Orchestrator
    participant HCE as 📋 HCE Parser
    participant RAG as 🧠 RAG Service
    participant LLM as 🤖 Gemini
    participant DB as 💾 PostgreSQL
    participant MONGO as 🍃 MongoDB

    U->>FE: Click "Generar EPC"
    FE->>API: POST /epc/{patient_id}/generate
    API->>ORC: orchestrate_generation()
    
    ORC->>MONGO: Fetch HCE raw data
    MONGO-->>ORC: HCE JSON
    
    ORC->>HCE: parse_hce()
    HCE-->>ORC: Structured data
    
    ORC->>RAG: get_similar_epcs()
    RAG-->>ORC: Few-shot examples
    
    ORC->>LLM: Generate with context
    LLM-->>ORC: Generated EPC text
    
    ORC->>DB: Save EPC
    DB-->>ORC: EPC ID
    
    ORC-->>API: EPC Response
    API-->>FE: JSON Response
    FE-->>U: Display EPC
```

### Arquitectura de Componentes

```mermaid
flowchart TB
    subgraph FRONTEND["🖥️ Frontend React"]
        UI[Interfaz Usuario]
        LOGIN[Login]
        PATIENTS[Pacientes]
        EPC_VIEW[Ver/Editar EPC]
        ADMIN[Panel Admin]
        TENANTS[Gestión Tenants]
    end

    subgraph BACKEND["⚙️ Backend FastAPI"]
        subgraph MIDDLEWARE["Middleware"]
            M_TENANT[Tenant Context]
            M_CORS[CORS]
            M_AUTH[JWT Auth]
        end

        subgraph ROUTERS["Routers API"]
            R_AUTH["/auth"]
            R_PATIENTS["/patients"]
            R_EPC["/epc"]
            R_HCE["/hce"]
            R_AINSTEIN["/ainstein"]
            R_ADMIN["/admin"]
            R_TENANTS["/admin/tenants"]
            R_EXTERNAL["/api/v1/external"]
        end

        subgraph SERVICES["Servicios"]
            S_AUTH[Security Service]
            S_PATIENT[Patient Service]
            S_EPC_ORC[EPC Orchestrator]
            S_EPC_SEC[Section Generator]
            S_AI[AI LangChain]
            S_RAG[RAG Service]
            S_FEEDBACK[Feedback Insights]
            S_PDF[PDF Service]
            S_RUST[Rust Engine]
        end

        subgraph REPOS["Repositorios"]
            REPO_USER[User Repo]
            REPO_PATIENT[Patient Repo]
            REPO_EPC[EPC Repo]
            REPO_HCE[HCE Repo]
        end
    end

    subgraph D2_LAYER["💾 D2 Data Layer"]
        subgraph TRUTH["Truth Core"]
            POSTGRES[(PostgreSQL<br/>+ RLS)]
        end
        subgraph EPHEMERAL["Ephemeral"]
            REDIS[(Redis)]
        end
        subgraph FLEXIBLE["Flexible"]
            MONGO[(MongoDB)]
        end
        subgraph VECTOR["Vector Brain"]
            QDRANT[(Qdrant)]
        end
    end

    subgraph EXTERNAL["🌐 Servicios Externos"]
        GEMINI[Google Gemini AI]
        AINSTEIN_WS[HCE WS API<br/>Markey]
    end

    %% Connections
    UI --> M_TENANT
    M_TENANT --> M_CORS
    M_CORS --> M_AUTH
    M_AUTH --> ROUTERS

    R_AUTH --> S_AUTH
    R_PATIENTS --> S_PATIENT
    R_EPC --> S_EPC_ORC
    S_EPC_ORC --> S_EPC_SEC
    S_EPC_SEC --> S_AI
    S_AI --> S_RAG
    R_AINSTEIN --> AINSTEIN_WS

    S_AUTH --> REPO_USER
    S_PATIENT --> REPO_PATIENT
    S_EPC_ORC --> REPO_EPC
    S_EPC_ORC --> REPO_HCE

    REPO_USER --> POSTGRES
    REPO_PATIENT --> POSTGRES
    REPO_EPC --> POSTGRES
    REPO_HCE --> MONGO

    S_AI --> GEMINI
    S_RAG --> QDRANT
    S_RUST --> REDIS

    classDef frontend fill:#61dafb,stroke:#21a1c4,color:#000
    classDef backend fill:#009688,stroke:#00695c,color:#fff
    classDef database fill:#ff9800,stroke:#e65100,color:#000
    classDef external fill:#9c27b0,stroke:#6a1b9a,color:#fff
```

### Flujo Multi-Tenant

```mermaid
flowchart LR
    subgraph TENANTS["Tenants"]
        T1[🏥 Clínica Markey]
        T2[🏥 Hospital San José]
        T3[🏥 Centro Médico XYZ]
    end

    subgraph API["API Layer"]
        MW[Tenant Middleware]
        RLS[RLS Policy]
    end

    subgraph DATA["Data Isolation"]
        DB1[(Tenant 1 Data)]
        DB2[(Tenant 2 Data)]
        DB3[(Tenant 3 Data)]
    end

    T1 -->|X-Tenant-ID: markey| MW
    T2 -->|X-Tenant-ID: sanjose| MW
    T3 -->|X-Tenant-ID: xyz| MW

    MW --> RLS
    RLS --> DB1
    RLS --> DB2
    RLS --> DB3
```

---

## 📡 API Endpoints

### Autenticación

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/auth/login` | Login con email/password |
| POST | `/auth/logout` | Logout (invalidar sesión) |
| GET | `/auth/me` | Obtener usuario actual |

### Pacientes

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/patients` | Listar pacientes (paginado) |
| GET | `/patients/{id}` | Obtener paciente |
| POST | `/patients` | Crear paciente |
| PUT | `/patients/{id}` | Actualizar paciente |

### EPC (Epicrisis)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/epc/{patient_id}/latest` | Obtener última EPC |
| POST | `/epc/{patient_id}/generate` | 🤖 Generar EPC con IA |
| PUT | `/epc/{id}` | Actualizar EPC |
| POST | `/epc/{id}/feedback` | Enviar feedback |
| GET | `/epc/{id}/history` | Historial de versiones |
| GET | `/epc/{id}/pdf` | Descargar PDF |

### HCE (Historia Clínica)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/hce/{patient_id}` | Obtener HCE de MongoDB |
| POST | `/hce/import` | Importar HCE desde JSON |

### HCE WebService (Multi-tenant)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/ainstein/episodios` | Obtener episodios de HCE externo |
| GET | `/ainstein/historia` | Obtener historia clínica externa |
| GET | `/ainstein/test-connection` | Probar conexión al WS |

### Admin

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/admin/health` | 🔍 Healthcheck completo |
| GET | `/admin/tenants` | Listar tenants |
| POST | `/admin/tenants` | Crear tenant |
| GET | `/admin/tenants/{id}/test-connection` | Probar conexión HCE |
| GET | `/epc/admin/feedback-dashboard` | Dashboard feedback IA |
| GET | `/epc/admin/llm-costs` | Costos LLM |

---

## 🏢 Multi-Tenancy

El sistema soporta múltiples tenants (clínicas/hospitales) con aislamiento completo de datos.

### Configurar Nuevo Tenant

1. **Crear tenant desde Admin Panel** o API:

```bash
curl -X POST http://localhost:8000/admin/tenants \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "sanjose",
    "name": "Hospital San José",
    "contact_email": "admin@sanjose.com",
    "integration_type": "inbound"
  }'
```

2. **Configurar credenciales HCE** (si tiene WS externo):

```bash
curl -X PUT http://localhost:8000/admin/tenants/{tenant_id}/config \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "external_endpoint": "https://api.sanjose.com/hce",
    "external_token": "token_secreto",
    "external_headers": "{\"http_method\": \"POST\"}"
  }'
```

3. **Probar conexión**:

```bash
curl http://localhost:8000/admin/tenants/{tenant_id}/test-connection \
  -H "Authorization: Bearer $TOKEN"
```

---

## ✅ Verificación del Sistema

Después de la instalación, verificar que todo funciona:

### Verificación Rápida

```bash
# 1. Verificar containers Docker
docker ps --format "table {{.Names}}\t{{.Status}}"

# 2. Verificar Rust engine
source .venv/bin/activate
python -c "import ainstein_core; print('✅ Rust OK')"

# 3. Verificar servidor
curl http://localhost:8000/
```

### Verificación Completa (Health Check)

```bash
# Obtener token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"tu_password"}' | jq -r '.access_token')

# Health check completo
curl -s http://localhost:8000/admin/health \
  -H "Authorization: Bearer $TOKEN" | jq
```

**Respuesta esperada:**
```json
{
  "status": "healthy",
  "services": {
    "docker": {"status": "ok"},
    "postgres": {"status": "ok"},
    "redis": {"status": "ok"},
    "mongodb": {"status": "ok"},
    "qdrant": {"status": "ok"},
    "rust_core": {"status": "ok"},
    "gemini_api": {"status": "ok"},
    "ainstein_ws": {"status": "ok"},
    "langchain": {"status": "ok"}
  }
}
```

Ver [docs/CHECKLIST_SISTEMA.md](docs/CHECKLIST_SISTEMA.md) para checklist completo.

---

## 🔧 Comandos Útiles

### Migraciones

```bash
# Ver estado actual
PYTHONPATH=. alembic current

# Crear nueva migración
PYTHONPATH=. alembic revision --autogenerate -m "descripcion"

# Aplicar todas las migraciones
PYTHONPATH=. alembic upgrade head

# Revertir última migración
PYTHONPATH=. alembic downgrade -1
```

### Desarrollo

```bash
# Iniciar servidor con reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Ver logs en tiempo real
tail -f backend.log

# Ejecutar con debug
uvicorn app.main:app --reload --log-level debug
```

### Docker

```bash
# Levantar todos los servicios
docker compose -f docker-compose.prod.yml up -d

# Ver logs de un servicio
docker logs -f ferro_postgres

# Reiniciar servicio
docker compose -f docker-compose.prod.yml restart mongo

# Detener todo
docker compose -f docker-compose.prod.yml down
```

### Base de Datos

```bash
# Conectar a PostgreSQL
docker exec -it ferro_postgres psql -U ainstein -d ainstein

# Conectar a MongoDB
docker exec -it ferro_mongo mongosh -u admin -p

# Backup PostgreSQL
docker exec ferro_postgres pg_dump -U ainstein ainstein > backup.sql

# Backup MongoDB
docker exec ferro_mongo mongodump --out /backup
```

---

## 🐛 Troubleshooting

| Problema | Solución |
|----------|----------|
| **`Tenant 'X' no tiene endpoint externo configurado`** | Ejecutar `PYTHONPATH=. python scripts/migrate_markey_to_tenant.py` |
| **`ModuleNotFoundError: ainstein_core`** | Recompilar: `cd rust_lib && maturin develop --release` |
| **Error conexión PostgreSQL** | Verificar container: `docker ps` y credenciales en `.env` |
| **Error conexión MongoDB** | Verificar `MONGO_URL` incluye `?authSource=admin` |
| **Error Gemini API** | Verificar `GEMINI_API_KEY` es válida |
| **CORS errors** | Agregar URL frontend a `CORS_ORIGINS` en `.env` |
| **401 Unauthorized** | Token expirado, re-loguearse |
| **Migraciones fallan** | Verificar `PYTHONPATH=.` antes de alembic |

---

## 📚 Documentación Adicional

- [CHECKLIST_SISTEMA.md](docs/CHECKLIST_SISTEMA.md) - Verificación completa del sistema
- [REGLAS_GENERACION_EPC.md](docs/REGLAS_GENERACION_EPC.md) - Reglas de negocio para EPCs

---

## 📄 Licencia

Propiedad de **Zeron Team** - Todos los derechos reservados.

---

*Última actualización: 2026-02-03 | FERRO D2 v3.0.0*