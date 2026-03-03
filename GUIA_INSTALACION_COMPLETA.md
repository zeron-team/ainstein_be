# 🏥 AInstein — Guía de Instalación Completa

> **Versión**: 3.0.0 (FERRO D2)  
> **Última actualización**: 28/02/2026  
> **Sistema Operativo recomendado**: Ubuntu 24.04 LTS o superior

---

## 📑 Índice

1. [Descripción General del Sistema](#1-descripción-general-del-sistema)
2. [Arquitectura y Stack Tecnológico](#2-arquitectura-y-stack-tecnológico)
3. [Prerequisitos del Servidor](#3-prerequisitos-del-servidor)
4. [Instalación de Dependencias del Sistema](#4-instalación-de-dependencias-del-sistema)
5. [Configuración de Bases de Datos](#5-configuración-de-bases-de-datos)
6. [Instalación del Backend](#6-instalación-del-backend)
7. [Instalación del Frontend](#7-instalación-del-frontend)
8. [Configuración de Nginx (Reverse Proxy)](#8-configuración-de-nginx-reverse-proxy)
9. [Servicios Systemd (Producción)](#9-servicios-systemd-producción)
10. [Restauración de Datos (Dumps)](#10-restauración-de-datos-dumps)
11. [Verificación Post-Instalación](#11-verificación-post-instalación)
12. [Estructura de Archivos Completa](#12-estructura-de-archivos-completa)
13. [Variables de Entorno — Referencia Completa](#13-variables-de-entorno--referencia-completa)
14. [Módulos del Sistema — Descripción Funcional](#14-módulos-del-sistema--descripción-funcional)
15. [Troubleshooting](#15-troubleshooting)

---

## 1. Descripción General del Sistema

**AInstein** es una plataforma de generación automática de **Epicrisis (EPC)** hospitalarias usando Inteligencia Artificial. El sistema:

- **Importa** Historias Clínicas Electrónicas (HCE) desde el sistema Markey/AInstein
- **Genera** Epicrisis automáticas usando Google Gemini (LLM)
- **Permite** a los médicos evaluar, corregir y aprobar las EPCs
- **Aprende** de las correcciones mediante un sistema de aprendizaje continuo
- **Exporta** las EPCs en formato PDF profesional

### Flujo Principal

```
HCE (Markey) → Importar → Parser → IA (Gemini) → EPC → Evaluación → Aprendizaje
```

---

## 2. Arquitectura y Stack Tecnológico

### Diagrama de Arquitectura

```
┌─────────────────────────────────────────────────────┐
│                  NGINX (Puerto 80/443)               │
│  ┌─────────────────┐     ┌───────────────────────┐  │
│  │  Frontend (SPA)  │     │  /api/ → Backend:8000 │  │
│  │  React + Vite    │     │  FastAPI + Uvicorn     │  │
│  └─────────────────┘     └───────────────────────┘  │
└─────────────────────────────────────────────────────┘
                            │
          ┌─────────────────┼──────────────────┐
          │                 │                  │
    ┌─────▼─────┐    ┌─────▼─────┐     ┌──────▼──────┐
    │ PostgreSQL │    │  MongoDB  │     │    Redis    │
    │  (Datos)   │    │ (Docs/IA) │     │   (Cache)   │
    │  Port 5432 │    │ Port 27017│     │  Port 6379  │
    └───────────┘    └───────────┘     └─────────────┘
                          │
                    ┌─────▼─────┐
                    │  Qdrant   │
                    │ (Vectores)│
                    │ Port 6333 │
                    └───────────┘
```

### Stack Completo

| Componente | Tecnología | Versión | Propósito |
|---|---|---|---|
| **OS** | Ubuntu | 24.04+ | Sistema operativo del servidor |
| **Runtime Backend** | Python | 3.12+ | Lenguaje del backend |
| **Framework Backend** | FastAPI | latest | API REST asíncrona |
| **Runtime Frontend** | Node.js | 24+ | Build del frontend |
| **Framework Frontend** | React | 18.3 | Interfaz de usuario |
| **Build Tool** | Vite | 5.4 | Bundler del frontend |
| **Lenguaje Frontend** | TypeScript | 5.6 | Tipado estático |
| **BD Relacional** | PostgreSQL | 16 | Usuarios, pacientes, admisiones |
| **BD Documental** | MongoDB | 7 | HCEs, EPCs, feedback, reglas |
| **Cache** | Redis | 7+ | Cache de sesiones y datos |
| **BD Vectorial** | Qdrant | latest | RAG y similaridad semántica |
| **IA/LLM** | Google Gemini | 2.0 Flash | Generación de EPCs |
| **Web Server** | Nginx | 1.26+ | Reverse proxy y archivos estáticos |
| **ORM SQL** | SQLAlchemy | latest | Mapeo objeto-relacional |
| **Migraciones SQL** | Alembic | latest | Migraciones de esquema SQL |
| **Driver MongoDB** | Motor (async) | latest | Conexión asíncrona a MongoDB |

---

## 3. Prerequisitos del Servidor

### Hardware Mínimo

| Recurso | Mínimo | Recomendado |
|---|---|---|
| CPU | 2 cores | 4 cores |
| RAM | 4 GB | 8 GB |
| Disco | 40 GB SSD | 100 GB SSD |
| Red | Acceso a internet (para API de Gemini) | - |

### Puertos Requeridos

| Puerto | Servicio | Acceso |
|---|---|---|
| 80 | Nginx (HTTP) | Público |
| 443 | Nginx (HTTPS) | Público (opcional) |
| 8000 | Backend FastAPI | Solo interno (localhost) |
| 5432 | PostgreSQL | Solo interno |
| 27017 | MongoDB | Solo interno |
| 6379 | Redis | Solo interno |
| 6333 | Qdrant | Solo interno |

---

## 4. Instalación de Dependencias del Sistema

### 4.1 Actualizar el Sistema

```bash
sudo apt update && sudo apt upgrade -y
```

### 4.2 Instalar Python 3.12+

```bash
sudo apt install -y python3 python3-pip python3-venv python3-dev
python3 --version  # Verificar: debe ser 3.12+
```

### 4.3 Instalar Node.js 24+ (via NodeSource)

```bash
# Instalar Node.js 24 LTS
curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash -
sudo apt install -y nodejs

node --version   # Verificar: v24+
npm --version    # Verificar: 11+
```

### 4.4 Instalar PostgreSQL 16

```bash
# Instalar PostgreSQL
sudo apt install -y postgresql postgresql-contrib

# Verificar que está corriendo
sudo systemctl status postgresql
sudo systemctl enable postgresql

psql --version  # Verificar: 16+
```

### 4.5 Instalar MongoDB 7

```bash
# Importar clave GPG de MongoDB
curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | \
  sudo gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor

# Agregar repositorio (ajustar para tu versión de Ubuntu)
echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | \
  sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list

sudo apt update
sudo apt install -y mongodb-org

# Iniciar y habilitar
sudo systemctl start mongod
sudo systemctl enable mongod

# Verificar
mongosh --eval "db.adminCommand('ping')"
```

> **Nota**: Si tu versión de Ubuntu no tiene paquete disponible, puedes usar Docker:
> ```bash
> docker run -d --name mongo -p 27017:27017 \
>   -e MONGO_INITDB_ROOT_USERNAME=admin \
>   -e MONGO_INITDB_ROOT_PASSWORD=tu_password_seguro \
>   -v mongo_data:/data/db \
>   mongo:7
> ```

### 4.6 Instalar Redis 7

```bash
sudo apt install -y redis-server

# Editar configuración para permitir systemd
sudo sed -i 's/^supervised no/supervised systemd/' /etc/redis/redis.conf

sudo systemctl restart redis
sudo systemctl enable redis

redis-cli ping  # Debe responder: PONG
```

### 4.7 Instalar Qdrant (Vector Database)

```bash
# Opción 1: Docker (recomendado)
docker run -d --name qdrant \
  -p 6333:6333 -p 6334:6334 \
  -v qdrant_data:/qdrant/storage \
  --restart unless-stopped \
  qdrant/qdrant:latest

# Verificar
curl http://localhost:6333/healthz  # Debe responder: {"title":"qdrant"...}
```

### 4.8 Instalar Nginx

```bash
sudo apt install -y nginx
sudo systemctl enable nginx
nginx -v  # Verificar instalación
```

### 4.9 Instalar Dependencias de Sistema para WeasyPrint (PDF)

```bash
# WeasyPrint necesita estas librerías para generar PDFs
sudo apt install -y libpango-1.0-0 libpangocairo-1.0-0 \
  libgdk-pixbuf2.0-0 libffi-dev shared-mime-info \
  libcairo2 libcairo2-dev libgirepository1.0-dev \
  gir1.2-pango-1.0 fonts-liberation
```

### 4.10 Instalar Git

```bash
sudo apt install -y git
```

---

## 5. Configuración de Bases de Datos

### 5.1 Configurar PostgreSQL

#### 5.1.1 Crear usuario y base de datos

```bash
# Acceder como usuario postgres
sudo -u postgres psql
```

Ejecutar en la consola de PostgreSQL:

```sql
-- Crear usuario
CREATE USER ainstein WITH PASSWORD 'ainstein_secure_2026';

-- Crear base de datos
CREATE DATABASE ainstein OWNER ainstein;

-- Otorgar permisos
GRANT ALL PRIVILEGES ON DATABASE ainstein TO ainstein;

-- Salir
\q
```

#### 5.1.2 Verificar conexión

```bash
psql -h localhost -U ainstein -d ainstein -c "SELECT 1;"
# Debe pedir password: ainstein_secure_2026
# Debe responder con una tabla con valor 1
```

### 5.2 Configurar MongoDB

#### 5.2.1 Crear usuario y base de datos

```bash
# Acceder a MongoDB como admin
mongosh
```

Ejecutar en la consola de MongoDB:

```javascript
// Usar la base de datos epc
use epc

// Crear usuario con permisos sobre la base 'epc'
db.createUser({
  user: "epc_user",
  pwd: "epc_strong_pass_2025",
  roles: [
    { role: "readWrite", db: "epc" }
  ]
})

// Verificar
db.auth("epc_user", "epc_strong_pass_2025")

// Salir
exit
```

#### 5.2.2 Habilitar autenticación en MongoDB

Editar el archivo de configuración:

```bash
sudo nano /etc/mongod.conf
```

Buscar la sección `security` y agregar/descomentar:

```yaml
security:
  authorization: enabled
```

Reiniciar MongoDB:

```bash
sudo systemctl restart mongod
```

#### 5.2.3 Verificar conexión autenticada

```bash
mongosh "mongodb://epc_user:epc_strong_pass_2025@localhost:27017/epc?authSource=epc" \
  --eval "db.stats()"
```

### 5.3 Verificar Redis

```bash
redis-cli ping
# Respuesta esperada: PONG

redis-cli info server | head -5
```

---

## 6. Instalación del Backend

### 6.1 Clonar el Repositorio

```bash
cd /home/ubuntu
mkdir -p aistein
cd aistein

# Clonar backend
git clone https://github.com/tu-org/ainstein_be.git backend

# Si ya está clonado, actualizar:
cd backend && git pull origin main
```

### 6.2 Crear Entorno Virtual Python

```bash
cd /home/ubuntu/aistein/backend

# Crear entorno virtual
python3 -m venv .venv

# Activar entorno virtual
source .venv/bin/activate

# Verificar que se está usando el Python del venv
which python3
# Debe mostrar: /home/ubuntu/aistein/backend/.venv/bin/python3
```

### 6.3 Instalar Dependencias Python

```bash
# Asegurar pip actualizado
pip install --upgrade pip

# Instalar todas las dependencias
pip install -r requirements.txt
```

> **Nota**: Si hay errores de compilación con WeasyPrint, verificar el paso 4.9.
> Si hay errores con psycopg2-binary, instalar: `sudo apt install libpq-dev`

#### Lista completa de dependencias (`requirements.txt`):

| Paquete | Propósito |
|---|---|
| `fastapi` | Framework web asíncrono |
| `uvicorn[standard]` | Servidor ASGI |
| `SQLAlchemy` | ORM para PostgreSQL |
| `alembic` | Migraciones de base de datos SQL |
| `psycopg2-binary` | Driver PostgreSQL |
| `motor` | Driver MongoDB asíncrono |
| `pymongo` | Driver MongoDB sincrónico |
| `redis>=5.0.0` | Cliente Redis |
| `PyJWT` | Autenticación JSON Web Token |
| `passlib[bcrypt]` | Hashing de contraseñas |
| `python-dotenv` | Variables de entorno |
| `pydantic[email]` | Validación de datos |
| `pydantic-settings` | Configuración desde .env |
| `httpx` | Cliente HTTP asíncrono |
| `jinja2` | Templates HTML |
| `weasyprint` | Generación de PDF |
| `pdfminer.six` | Lectura de PDFs |
| `python-multipart` | Upload de archivos |
| `llama-index-core` | Framework de IA |
| `llama-index-llms-gemini` | Integración con Google Gemini |
| `llama-index-embeddings-gemini` | Embeddings de Gemini |
| `llama-index-vector-stores-qdrant` | Almacén vectorial |
| `qdrant-client` | Cliente Qdrant |
| `opentelemetry-*` | Observabilidad y tracing |

### 6.4 Configurar Variables de Entorno

Crear el archivo `.env` en la raíz del backend:

```bash
nano /home/ubuntu/aistein/backend/.env
```

Contenido completo del archivo `.env`:

```env
# ==============================================================================
# BASE DE DATOS
# ==============================================================================

# PostgreSQL: Usuarios, pacientes, admisiones, roles
SQL_URL=postgresql://ainstein:ainstein_secure_2026@localhost:5432/ainstein

# MongoDB: HCEs, EPCs, feedback, reglas aprendidas, logs
MONGO_URL=mongodb://epc_user:epc_strong_pass_2025@127.0.0.1:27017/epc?authSource=epc

# Redis: Cache de sesiones, rate limiting
REDIS_URL=redis://localhost:6379/0

# ==============================================================================
# AUTENTICACIÓN
# ==============================================================================

# Secreto para firmar JWT tokens (CAMBIAR en producción)
JWT_SECRET=pon_un_secreto_largo_y_unico_aqui_minimo_32_caracteres
JWT_EXPIRE_MINUTES=120

# ==============================================================================
# INTELIGENCIA ARTIFICIAL (Google Gemini)
# ==============================================================================

# API Key de Google AI Studio (https://aistudio.google.com/apikey)
GEMINI_API_KEY=tu_api_key_de_google_gemini_aqui
GEMINI_MODEL=gemini-2.0-flash
GEMINI_API_HOST=https://generativelanguage.googleapis.com
GEMINI_API_VERSION=v1beta

# ==============================================================================
# CORS (Orígenes permitidos)
# ==============================================================================

# JSON array de los dominios que pueden acceder a la API
# Incluir localhost para desarrollo y tu dominio de producción
CORS_ORIGINS=["http://localhost:5173","http://TU_IP_PUBLICA","https://tu-dominio.com"]

# ==============================================================================
# UPLOADS
# ==============================================================================

HCE_UPLOAD_DIR=/tmp/hce_uploads

# ==============================================================================
# INTEGRACIÓN AINSTEIN/MARKEY (Sistema externo de HCE)
# ==============================================================================

AINSTEIN_HTTP_METHOD=GET
AINSTEIN_API_URL=https://ainstein1.markeyoci.com.ar/obtener
AINSTEIN_APP=AInstein
AINSTEIN_API_KEY=tu_api_key_markey
AINSTEIN_TOKEN=tu_token_markey
AINSTEIN_TIMEOUT_SECONDS=60

# ==============================================================================
# QDRANT (Base de datos vectorial para RAG)
# ==============================================================================

QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_ENABLED=true

# ==============================================================================
# RAG (Retrieval Augmented Generation)
# ==============================================================================

RAG_ENABLED=true
RAG_FEW_SHOT_EXAMPLES=3
```

### 6.5 Ejecutar Migraciones de Base de Datos (PostgreSQL)

Las migraciones crean las tablas en PostgreSQL:

```bash
cd /home/ubuntu/aistein/backend

# Activar venv si no está activado
source .venv/bin/activate

# Ejecutar migraciones de Alembic
alembic upgrade head
```

Esto crea las siguientes tablas en PostgreSQL:

| Tabla | Descripción |
|---|---|
| `roles` | Roles del sistema (admin, medico, viewer) |
| `users` | Usuarios del sistema |
| `patients` | Datos de pacientes |
| `patient_status` | Estado actual de cada paciente |
| `admissions` | Admisiones hospitalarias |
| `tenants` | Tenants para multi-tenancy |
| `alembic_version` | Control de versiones de migraciones |

### 6.6 Crear Usuario Administrador

```bash
cd /home/ubuntu/aistein/backend
source .venv/bin/activate

python3 create_admin_user.py
```

Esto crea:
- **Roles**: `admin`, `medico`, `viewer`
- **Usuario admin**: `admin` / `Admin123!` / `admin@example.com`

> ⚠️ **IMPORTANTE**: Cambiar la contraseña en producción.

### 6.7 Crear Directorio de Uploads

```bash
mkdir -p /tmp/hce_uploads
chmod 755 /tmp/hce_uploads
```

### 6.8 Verificar que el Backend Arranca

```bash
cd /home/ubuntu/aistein/backend
source .venv/bin/activate

# Iniciar el servidor de prueba
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Salida esperada:

```
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

Verificar en otra terminal:

```bash
# Health check
curl http://localhost:8000/
# Respuesta: {"ok":true,"service":"EPC Suite"}

# Documentación interactiva
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/docs
# Respuesta: 200
```

Detener con `Ctrl+C`.

---

## 7. Instalación del Frontend

### 7.1 Clonar el Repositorio

```bash
cd /home/ubuntu/aistein

# Clonar frontend
git clone https://github.com/tu-org/ainstein_fe.git frontend

# Si ya está clonado, actualizar:
cd frontend && git pull origin main
```

### 7.2 Instalar Dependencias Node.js

```bash
cd /home/ubuntu/aistein/frontend

# Instalar todas las dependencias
npm install
```

#### Dependencias principales (`package.json`):

| Paquete | Propósito |
|---|---|
| `react`, `react-dom` | Librería de UI |
| `react-router-dom` | Navegación SPA |
| `axios` | Cliente HTTP para llamadas a la API |
| `react-icons` | Íconos |
| `jspdf`, `jspdf-autotable` | Generación de PDFs en el cliente |
| `xlsx` | Exportación de datos a Excel |
| `file-saver` | Descarga de archivos |
| `classnames` | Utilidad de CSS |

### 7.3 Configurar Variables de Entorno del Frontend

Crear el archivo `.env`:

```bash
nano /home/ubuntu/aistein/frontend/.env
```

Contenido:

```env
# URL base de la API
# En producción: apunta al dominio con /api
VITE_API_URL=https://tu-dominio.com
```

> **Nota**: El frontend hace las llamadas a `VITE_API_URL/api/...`. Nginx se encarga de hacer el proxy de `/api/` al backend en el puerto 8000.

### 7.4 Compilar el Frontend (Build de Producción)

```bash
cd /home/ubuntu/aistein/frontend

# Compilar TypeScript y crear bundle de producción
npx tsc -b && npx vite build
```

Salida esperada:

```
vite v5.4.x building for production...
transforming...
✓ 527 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                 4.54 kB │ gzip:  1.48 kB
dist/assets/index-XXXXX.css   205.62 kB │ gzip: 36.00 kB
dist/assets/index-XXXXX.js  1,335.15 kB │ gzip: 411.16 kB
✓ built in X.XXs
```

Los archivos compilados se encuentran en `/home/ubuntu/aistein/frontend/dist/`.

### 7.5 Copiar Build al Directorio de Nginx

```bash
# Crear directorio de destino
sudo mkdir -p /var/www/html/aistein-frontend

# Copiar archivos compilados
sudo cp -r /home/ubuntu/aistein/frontend/dist/* /var/www/html/aistein-frontend/

# Verificar
ls -la /var/www/html/aistein-frontend/
# Debe contener: index.html, assets/, favicon.png, etc.
```

---

## 8. Configuración de Nginx (Reverse Proxy)

### 8.1 Crear Configuración de Nginx

```bash
sudo nano /etc/nginx/sites-available/ainstein
```

Contenido completo:

```nginx
server {
    listen 80 default_server;
    listen [::]:80 default_server;

    # Permitir uploads grandes (HCEs en PDF)
    client_max_body_size 50M;

    server_name _;

    # ============================================================
    # Frontend React (archivos estáticos del build)
    # ============================================================
    root /var/www/html/aistein-frontend;
    index index.html;

    # index.html: SIN cache (para que tome nuevos builds)
    location = /index.html {
        add_header Cache-Control "no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0" always;
    }

    # assets con hash de Vite: cache largo e inmutable
    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable" always;
        try_files $uri =404;
    }

    # SPA fallback: todas las rutas van a index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # ============================================================
    # Backend FastAPI (Reverse Proxy)
    # ============================================================
    # /api/auth/login → http://127.0.0.1:8000/auth/login
    location /api/ {
        proxy_pass http://127.0.0.1:8000/;

        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
    }
}
```

### 8.2 Activar el Sitio

```bash
# Eliminar configuración default si existe
sudo rm -f /etc/nginx/sites-enabled/default

# Crear enlace simbólico
sudo ln -sf /etc/nginx/sites-available/ainstein /etc/nginx/sites-enabled/ainstein

# Verificar sintaxis
sudo nginx -t
# Debe mostrar: syntax is ok / test is successful

# Recargar Nginx
sudo systemctl reload nginx
```

---

## 9. Servicios Systemd (Producción)

### 9.1 Crear Servicio para el Backend

```bash
sudo nano /etc/systemd/system/ainstein-backend.service
```

Contenido:

```ini
[Unit]
Description=AInstein Backend (FastAPI + Uvicorn)
After=network.target postgresql.service mongod.service redis.service
Wants=postgresql.service mongod.service redis.service

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/aistein/backend
Environment="PATH=/home/ubuntu/aistein/backend/.venv/bin:/usr/local/bin:/usr/bin"
ExecStart=/home/ubuntu/aistein/backend/.venv/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
StandardOutput=append:/var/log/ainstein-backend.log
StandardError=append:/var/log/ainstein-backend-error.log

[Install]
WantedBy=multi-user.target
```

### 9.2 Activar y Arrancar el Backend

```bash
# Recargar servicios
sudo systemctl daemon-reload

# Habilitar arranque automático
sudo systemctl enable ainstein-backend

# Iniciar el servicio
sudo systemctl start ainstein-backend

# Verificar estado
sudo systemctl status ainstein-backend
# Debe mostrar: active (running)

# Ver logs en tiempo real
sudo journalctl -u ainstein-backend -f
```

### 9.3 Comandos Útiles de Gestión

```bash
# Reiniciar backend (después de cambios en código)
sudo systemctl restart ainstein-backend

# Detener backend
sudo systemctl stop ainstein-backend

# Ver últimos 50 logs
sudo journalctl -u ainstein-backend -n 50

# Rebuild y deploy del frontend
cd /home/ubuntu/aistein/frontend
npx tsc -b && npx vite build
sudo cp -r dist/* /var/www/html/aistein-frontend/
```

---

## 10. Restauración de Datos (Dumps)

Si tienes dumps de una instalación previa, sigue estos pasos para restaurarlos.

### 10.1 Ubicación de los Dumps

```
/home/ubuntu/aistein/backend/dump_20260228/
├── postgres_epc_db_full.sql          # Dump completo de PostgreSQL
├── mongo_epc_full/                   # Dump de MongoDB (colecciones .bson.gz)
│   ├── epc_docs.bson.gz
│   ├── epc_feedback.bson.gz
│   ├── hce_docs.bson.gz
│   ├── learning_rules.bson.gz
│   └── ... (30+ colecciones)
├── redis_dump.rdb                    # Dump de Redis
├── qdrant_hce_chunks.snapshot        # Snapshot de Qdrant (HCE chunks)
└── qdrant_epc_feedback.snapshot      # Snapshot de Qdrant (feedback vectors)
```

### 10.2 Restaurar PostgreSQL

```bash
# Borrar y recrear la base de datos
sudo -u postgres psql -c "DROP DATABASE IF EXISTS ainstein;"
sudo -u postgres psql -c "CREATE DATABASE ainstein OWNER ainstein;"

# Restaurar el dump
sudo -u postgres psql -d ainstein < /home/ubuntu/aistein/backend/dump_20260228/postgres_epc_db_full.sql

# Verificar
psql -h localhost -U ainstein -d ainstein -c "SELECT count(*) FROM patients;"
```

### 10.3 Restaurar MongoDB

```bash
# Descomprimir los archivos .bson.gz
cd /home/ubuntu/aistein/backend/dump_20260228/mongo_epc_full
for f in *.bson.gz; do gunzip -k "$f" 2>/dev/null; done

# Restaurar con mongorestore
mongorestore \
  --uri="mongodb://epc_user:epc_strong_pass_2025@localhost:27017/epc?authSource=epc" \
  --db=epc \
  --dir=/home/ubuntu/aistein/backend/dump_20260228/mongo_epc_full \
  --drop

# Verificar
mongosh "mongodb://epc_user:epc_strong_pass_2025@localhost:27017/epc?authSource=epc" \
  --eval "db.getCollectionNames()"
```

### 10.4 Restaurar Redis

```bash
# Detener Redis
sudo systemctl stop redis

# Copiar dump
sudo cp /home/ubuntu/aistein/backend/dump_20260228/redis_dump.rdb /var/lib/redis/dump.rdb
sudo chown redis:redis /var/lib/redis/dump.rdb

# Reiniciar Redis
sudo systemctl start redis

# Verificar
redis-cli dbsize
```

### 10.5 Restaurar Qdrant

```bash
# Restaurar snapshot de HCE chunks
curl -X POST "http://localhost:6333/collections/hce_chunks/snapshots/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "snapshot=@/home/ubuntu/aistein/backend/dump_20260228/qdrant_hce_chunks.snapshot"

# Restaurar snapshot de feedback vectors
curl -X POST "http://localhost:6333/collections/epc_feedback/snapshots/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "snapshot=@/home/ubuntu/aistein/backend/dump_20260228/qdrant_epc_feedback.snapshot"

# Verificar colecciones
curl http://localhost:6333/collections
```

---

## 11. Verificación Post-Instalación

### 11.1 Checklist de Servicios

Ejecutar cada comando y verificar la respuesta:

```bash
echo "=== 1. PostgreSQL ==="
psql -h localhost -U ainstein -d ainstein -c "SELECT count(*) FROM users;" 2>/dev/null && echo "✅ OK" || echo "❌ ERROR"

echo "=== 2. MongoDB ==="
mongosh "mongodb://epc_user:epc_strong_pass_2025@localhost:27017/epc?authSource=epc" \
  --quiet --eval "db.stats().collections" && echo "✅ OK" || echo "❌ ERROR"

echo "=== 3. Redis ==="
redis-cli ping && echo "✅ OK" || echo "❌ ERROR"

echo "=== 4. Qdrant ==="
curl -s http://localhost:6333/healthz && echo " ✅ OK" || echo "❌ ERROR"

echo "=== 5. Backend ==="
curl -s http://localhost:8000/ && echo " ✅ OK" || echo "❌ ERROR"

echo "=== 6. Nginx/Frontend ==="
curl -s -o /dev/null -w "%{http_code}" http://localhost/ && echo " ✅ OK" || echo "❌ ERROR"
```

### 11.2 Verificar Login

```bash
# Intentar login con el usuario admin
curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Admin123!"}' | python3 -m json.tool
```

Respuesta esperada:

```json
{
    "access_token": "eyJ...",
    "token_type": "bearer",
    "user": {
        "id": "...",
        "username": "admin",
        "role": "admin"
    }
}
```

### 11.3 Verificar Health Check Completo

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Admin123!"}' | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

curl -s http://localhost:8000/admin/health \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Esto muestra el estado de todos los servicios internos (PostgreSQL, MongoDB, Redis, Qdrant).

---

## 12. Estructura de Archivos Completa

### Backend (`/home/ubuntu/aistein/backend`)

```
backend/
├── .env                          # Variables de entorno (NO commitear)
├── .venv/                        # Entorno virtual Python
├── requirements.txt              # Dependencias Python
├── alembic.ini                   # Configuración de Alembic (migraciones)
├── create_admin_user.py          # Script para crear usuario admin
├── docker-compose.prod.yml       # Orquestación Docker (alternativa)
│
├── app/                          # Código principal de la aplicación
│   ├── __init__.py
│   ├── main.py                   # Entry point FastAPI (registra routers)
│   │
│   ├── core/                     # Configuración y utilidades core
│   │   ├── config.py             # Settings (lee .env)
│   │   ├── deps.py               # Dependencias de inyección (auth, DB)
│   │   ├── security.py           # Hashing de contraseñas (bcrypt)
│   │   ├── redis.py              # Conexión Redis
│   │   ├── redis_client.py       # Cliente Redis con cache
│   │   ├── telemetry.py          # OpenTelemetry (observabilidad)
│   │   ├── tenant.py             # Middleware multi-tenant
│   │   ├── tenant_context.py     # Contexto de tenant
│   │   ├── abac.py               # Control de acceso basado en atributos
│   │   └── pii_filter.py         # Filtro de datos personales
│   │
│   ├── adapters/                 # Adaptadores de infraestructura
│   │   └── mongo_client.py       # Conexión MongoDB y gestión de índices
│   │
│   ├── db/                       # Base de datos SQL
│   │   ├── base.py               # Base declarativa de SQLAlchemy
│   │   ├── session.py            # Engine y SessionLocal
│   │   └── migrations/           # Migraciones de Alembic
│   │       ├── env.py            # Configuración de Alembic
│   │       └── versions/         # Versiones de migraciones
│   │
│   ├── domain/                   # Modelos y esquemas
│   │   ├── models.py             # Modelos SQLAlchemy (User, Patient, etc.)
│   │   ├── schemas.py            # Schemas Pydantic (request/response)
│   │   ├── enums.py              # Enumeraciones
│   │   └── interfaces/           # Interfaces abstractas
│   │
│   ├── routers/                  # Endpoints API (controladores)
│   │   ├── auth.py               # POST /auth/login (JWT)
│   │   ├── users.py              # CRUD de usuarios (/admin/users)
│   │   ├── patients.py           # CRUD de pacientes (/patients)
│   │   ├── admissions.py         # Admisiones (/admissions)
│   │   ├── hce.py                # Gestión de HCE (/hce)
│   │   ├── epc.py                # ★ Módulo principal: generación EPC,
│   │   │                         #   feedback, diccionario, dashboard
│   │   ├── stats.py              # Estadísticas (/stats)
│   │   ├── config.py             # Configuración (/config)
│   │   ├── ainstein.py           # Integración Markey WS (/ainstein)
│   │   ├── golden_rules.py       # Reglas de Oro (/admin/golden-rules)
│   │   ├── health.py             # Health check (/admin/health)
│   │   ├── tenants.py            # Multi-tenant (/admin/tenants)
│   │   ├── snomed.py             # SNOMED CT (/admin/snomed)
│   │   ├── ingest.py             # Ingesta de datos (/api/ingest)
│   │   └── external.py           # API externa (/api/v1)
│   │
│   ├── services/                 # Lógica de negocio
│   │   ├── ai_langchain_service.py    # ★ Generación EPC con LangChain
│   │   │                              #   Incluye post-procesamiento,
│   │   │                              #   diccionario de reglas y golden rules
│   │   ├── ai_gemini_service.py       # Servicio Gemini (legacy/fallback)
│   │   ├── ai_llamaindex_service.py   # Servicio LlamaIndex (alternativo)
│   │   ├── hce_json_parser.py         # ★ Parser de HCE JSON (Markey)
│   │   ├── hce_ainstein_parser.py     # Parser de HCE específico AInstein
│   │   ├── hce_parser.py             # Parser base de HCE
│   │   ├── epc_section_generator.py   # Generación por secciones
│   │   ├── epc_pre_validator.py       # Validación pre-generación
│   │   ├── epc_history.py             # Historial de versiones
│   │   ├── feedback_insights_service.py # Insights del feedback
│   │   ├── feedback_llm_analyzer.py   # Análisis LLM del feedback
│   │   ├── golden_rules_service.py    # Servicio de Reglas de Oro
│   │   ├── patient_service.py         # Servicio de pacientes
│   │   ├── estudios_rules.py          # Reglas de estudios
│   │   ├── llm_usage_tracker.py       # Rastreo de costos LLM
│   │   ├── rag_service.py             # RAG (Retrieval Augmented Generation)
│   │   ├── vector_service.py          # Servicio de vectores
│   │   ├── redis_cache.py             # Cache Redis
│   │   ├── rust_engine.py             # Motor Rust (optimizaciones)
│   │   ├── tenant_rules_service.py    # Reglas por tenant
│   │   └── ingest_service.py          # Servicio de ingesta
│   │
│   ├── rules/                    # Módulo de reglas determinísticas
│   │   ├── death_detection.py    # Detección de fallecimiento
│   │   └── medication_classifier.py # Clasificación de medicación
│   │
│   ├── templates/                # Templates HTML
│   │   └── epc_pdf.html          # Template para PDF de EPC
│   │
│   └── utils/                    # Utilidades varias
│
├── scripts/                      # Scripts de mantenimiento
├── docs/                         # Documentación técnica
└── dump_20260228/                # Dumps de bases de datos
```

### Frontend (`/home/ubuntu/aistein/frontend`)

```
frontend/
├── .env                          # Variables de entorno (VITE_API_URL)
├── package.json                  # Dependencias Node.js
├── vite.config.ts                # Configuración de Vite
├── tsconfig.json                 # Configuración de TypeScript
├── index.html                    # HTML principal (entry point)
├── favicon.png                   # Ícono del sitio
├── Isologo_AInstein.png          # Logo de AInstein
│
├── src/                          # Código fuente
│   ├── main.tsx                  # Entry point React
│   ├── App.tsx                   # Componente raíz
│   ├── router.tsx                # Definición de rutas (React Router)
│   ├── index.css                 # Estilos globales / Design tokens
│   ├── vite-env.d.ts             # Tipos de Vite
│   │
│   ├── api/                      # Cliente HTTP
│   │   └── axiosClient.ts        # Configuración de Axios (base URL, JWT)
│   │
│   ├── auth/                     # Autenticación
│   │   ├── AuthContext.tsx        # Context de autenticación
│   │   ├── PrivateRoute.tsx       # Ruta protegida (requiere login)
│   │   └── PublicRoute.tsx        # Ruta pública (redirect si logueado)
│   │
│   ├── components/               # Componentes reutilizables
│   │   ├── layout/               # Layout principal
│   │   │   ├── AppLayout.tsx      # Layout con header + sidebar + footer
│   │   │   ├── Header.tsx         # Barra superior
│   │   │   ├── Sidebar.tsx        # Menú lateral
│   │   │   └── Footer.tsx         # Pie de página
│   │   ├── KPI.tsx               # Componente de KPI
│   │   ├── ImportHceModal.tsx    # Modal de importación de HCE
│   │   ├── HelpModal.tsx         # Modal de ayuda
│   │   └── EpcHistoryTimeline.jsx # Timeline de historial
│   │
│   ├── pages/                    # Páginas (vistas)
│   │   ├── Login.tsx             # Página de login
│   │   ├── Welcome.tsx           # Página de bienvenida
│   │   ├── Dashboard.tsx         # Dashboard principal
│   │   ├── ErrorPage.tsx         # Página de error 404
│   │   ├── AinsteinWsPage.tsx    # WebService AInstein/Markey
│   │   │
│   │   ├── Patients/             # Módulo Pacientes
│   │   │   ├── List.tsx          # Lista de pacientes
│   │   │   └── Form.tsx          # Formulario de paciente
│   │   │
│   │   ├── EPC/                  # Módulo EPC
│   │   │   └── ViewEdit.tsx      # ★ Vista/Edición de EPC (principal)
│   │   │
│   │   ├── Admin/                # Módulo Administración
│   │   │   ├── EPCControlDashboard.tsx  # Control de evaluaciones
│   │   │   ├── FeedbackDashboard.tsx    # Dashboard de feedback
│   │   │   ├── CostsDashboard.tsx       # Costos de LLM
│   │   │   ├── GoldenRules.tsx          # Reglas de Oro
│   │   │   ├── HealthCheck.tsx          # Health check
│   │   │   ├── TenantManager.tsx        # Gestión de tenants
│   │   │   └── SnomedDashboard.tsx      # SNOMED CT
│   │   │
│   │   ├── Users/                # Módulo Usuarios
│   │   │   └── UsersCRUD.tsx     # CRUD de usuarios
│   │   │
│   │   └── Settings/             # Configuración
│   │       └── Branding.tsx      # Personalización visual
│   │
│   ├── styles/                   # Estilos CSS
│   │   ├── design-tokens.css     # Variables CSS globales
│   │   ├── components.css        # Estilos de componentes
│   │   └── utilities.css         # Utilidades CSS
│   │
│   └── types/                    # Tipos TypeScript
│       └── index.ts              # Definiciones de tipos
│
└── dist/                         # Build compilado (se copia a Nginx)
```

---

## 13. Variables de Entorno — Referencia Completa

### Backend (`.env`)

| Variable | Obligatoria | Ejemplo | Descripción |
|---|---|---|---|
| `SQL_URL` | ✅ Sí | `postgresql://ainstein:pass@localhost:5432/ainstein` | Conexión PostgreSQL |
| `MONGO_URL` | ✅ Sí | `mongodb://user:pass@localhost:27017/epc?authSource=epc` | Conexión MongoDB |
| `REDIS_URL` | ✅ Sí | `redis://localhost:6379/0` | Conexión Redis |
| `JWT_SECRET` | ✅ Sí | `secreto_largo_unico_32chars` | Secreto para tokens JWT |
| `JWT_EXPIRE_MINUTES` | No | `120` | Expiración de token (minutos) |
| `GEMINI_API_KEY` | ✅ Sí | `AIzaSy...` | API Key de Google AI Studio |
| `GEMINI_MODEL` | No | `gemini-2.0-flash` | Modelo de Gemini a usar |
| `GEMINI_API_HOST` | No | `https://generativelanguage.googleapis.com` | Host de la API |
| `GEMINI_API_VERSION` | No | `v1beta` | Versión de la API |
| `CORS_ORIGINS` | No | `["http://localhost:5173"]` | Orígenes CORS permitidos |
| `HCE_UPLOAD_DIR` | No | `/tmp/hce_uploads` | Directorio para uploads |
| `AINSTEIN_API_URL` | No | `https://ainstein1.markeyoci...` | URL de API Markey |
| `AINSTEIN_APP` | No | `AInstein` | Nombre de app en Markey |
| `AINSTEIN_API_KEY` | No | `uuid...` | API Key de Markey |
| `AINSTEIN_TOKEN` | No | `token_largo...` | Token de Markey |
| `AINSTEIN_TIMEOUT_SECONDS` | No | `60` | Timeout de consulta |
| `QDRANT_HOST` | No | `localhost` | Host de Qdrant |
| `QDRANT_PORT` | No | `6333` | Puerto de Qdrant |
| `QDRANT_ENABLED` | No | `true` | Habilitar Qdrant |
| `RAG_ENABLED` | No | `true` | Habilitar RAG |
| `RAG_FEW_SHOT_EXAMPLES` | No | `3` | Cantidad de ejemplos RAG |

### Frontend (`.env`)

| Variable | Obligatoria | Ejemplo | Descripción |
|---|---|---|---|
| `VITE_API_URL` | ✅ Sí | `https://www.ainstein-epc.com` | URL base del servidor |

---

## 14. Módulos del Sistema — Descripción Funcional

### 14.1 Rutas del Frontend

| Ruta | Página | Rol | Descripción |
|---|---|---|---|
| `/login` | Login | Público | Inicio de sesión |
| `/` | Welcome | Logueado | Página de bienvenida |
| `/dashboard` | Dashboard | Logueado | Dashboard con KPIs |
| `/patients` | Lista Pacientes | Logueado | Lista y búsqueda de pacientes |
| `/patients/new` | Form Paciente | Logueado | Crear paciente |
| `/epc/:id` | Vista/Edición EPC | Logueado | Ver y editar EPC generada |
| `/ainstein` | WebService | Logueado | Importar HCE desde Markey |
| `/admin/users` | Usuarios | Admin | CRUD de usuarios |
| `/admin/feedback` | Feedback | Admin | Dashboard de feedback |
| `/admin/costs` | Costos | Admin | Costos de LLM |
| `/admin/health` | Health | Admin | Estado de servicios |
| `/admin/tenants` | Tenants | Admin | Multi-tenancy |
| `/admin/epc-control` | Control EPC | Admin | Control de evaluaciones |
| `/admin/snomed` | SNOMED | Admin | SNOMED CT Argentina |
| `/admin/golden-rules` | Reglas de Oro | Admin | Configuración de reglas IA |

### 14.2 Endpoints API Principales

| Método | Endpoint | Descripción |
|---|---|---|
| `POST` | `/auth/login` | Login y obtención de JWT |
| `GET` | `/patients` | Lista de pacientes |
| `POST` | `/patients` | Crear paciente |
| `GET` | `/epc/{id}` | Obtener EPC |
| `POST` | `/epc/generate` | Generar EPC con IA |
| `PUT` | `/epc/{id}` | Actualizar EPC |
| `POST` | `/epc/{id}/feedback` | Enviar feedback de evaluación |
| `POST` | `/epc/{id}/feedback/complete` | Completar evaluación |
| `GET` | `/epc/feedback/stats` | Estadísticas de feedback |
| `GET` | `/epc/admin/dashboard-control` | Dashboard de control |
| `GET` | `/epc/feedback/section-dictionary` | Diccionario de secciones |
| `GET` | `/admin/golden-rules` | Reglas de Oro |
| `PUT` | `/admin/golden-rules/{section}` | Actualizar regla |
| `GET` | `/admin/health` | Health check |
| `GET` | `/admin/tenants` | Listar tenants |
| `GET` | `/hce/{patient_id}` | Obtener HCE de paciente |

### 14.3 Colecciones MongoDB

| Colección | Descripción |
|---|---|
| `hce_docs` | Documentos de Historia Clínica Electrónica |
| `epc_docs` | Documentos de Epicrisis generadas |
| `epc_versions` | Versiones históricas de EPCs |
| `epc_feedback` | Evaluaciones de médicos |
| `epc_logs` | Logs de operaciones (TTL 30 días) |
| `epc_section_corrections` | Correcciones de secciones pendientes |
| `section_mapping_dictionary` | Diccionario aprendido de secciones |
| `golden_rules` | Reglas de Oro configuradas |
| `learning_rules` | Reglas aprendidas por LLM |
| `learning_problems` | Problemas detectados por LLM |
| `chat_history` | Historial de chat (TTL 7 días) |
| `llm_usage` | Uso y costos de LLM (TTL 90 días) |
| `tenants` | Configuración multi-tenant |
| `tenant_rules` | Reglas específicas por tenant |

### 14.4 Tablas PostgreSQL

| Tabla | Descripción |
|---|---|
| `roles` | Roles del sistema (admin, medico, viewer) |
| `users` | Usuarios registrados |
| `patients` | Datos demográficos de pacientes |
| `patient_status` | Estado actual de cada paciente |
| `admissions` | Admisiones hospitalarias |
| `tenants` | Organizaciones/tenants |
| `alembic_version` | Versión de migraciones |

---

## 15. Troubleshooting

### Error: "ModuleNotFoundError"

```bash
# Asegurarse de estar usando el venv correcto
cd /home/ubuntu/aistein/backend
source .venv/bin/activate
pip install -r requirements.txt
```

### Error: "Connection refused" en MongoDB

```bash
# Verificar que MongoDB está corriendo
sudo systemctl status mongod

# Si no arranca, verificar logs
sudo cat /var/log/mongodb/mongod.log | tail -20

# Verificar que la autenticación está configurada
mongosh "mongodb://epc_user:epc_strong_pass_2025@localhost:27017/epc?authSource=epc" --eval "db.stats()"
```

### Error: "CORS" en el frontend

1. Verificar que la IP/dominio del frontend está en `CORS_ORIGINS` del `.env`
2. Reiniciar el backend: `sudo systemctl restart ainstein-backend`

### Error: "502 Bad Gateway" en Nginx

```bash
# Verificar que el backend está corriendo
curl http://localhost:8000/
# Si no responde:
sudo systemctl restart ainstein-backend
sudo systemctl status ainstein-backend
```

### Error: "WeasyPrint" al generar PDFs

```bash
# Instalar dependencias de sistema
sudo apt install -y libpango-1.0-0 libpangocairo-1.0-0 \
  libgdk-pixbuf2.0-0 libffi-dev shared-mime-info \
  libcairo2 fonts-liberation
```

### Frontend no muestra cambios después de deploy

```bash
# Limpiar cache de Nginx
sudo nginx -t && sudo systemctl reload nginx

# En el navegador: Ctrl+Shift+R (hard reload)
```

### Cómo actualizar la aplicación

```bash
# 1. Actualizar backend
cd /home/ubuntu/aistein/backend
git pull origin main
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
sudo systemctl restart ainstein-backend

# 2. Actualizar frontend
cd /home/ubuntu/aistein/frontend
git pull origin main
npm install
npx tsc -b && npx vite build
sudo cp -r dist/* /var/www/html/aistein-frontend/
```

---

> **Documento generado el 28/02/2026**  
> **AInstein v3.0.0 — FERRO D2**
