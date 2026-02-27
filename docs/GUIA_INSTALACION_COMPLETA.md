# 🏥 AInstein — Guía de Instalación Completa

> Guía paso a paso para instalar la plataforma AInstein desde cero en un servidor Ubuntu.
> Última actualización: 2026-02-27

---

## 📋 Tabla de Contenidos

1. [Resumen de la Plataforma](#1-resumen-de-la-plataforma)
2. [Requisitos del Servidor](#2-requisitos-del-servidor)
3. [Preparar el Servidor](#3-preparar-el-servidor)
4. [Instalar Docker y Contenedores](#4-instalar-docker-y-contenedores)
5. [Instalar y Configurar el Backend](#5-instalar-y-configurar-el-backend)
6. [Instalar y Configurar el Frontend](#6-instalar-y-configurar-el-frontend)
7. [Configurar Nginx (Reverse Proxy)](#7-configurar-nginx-reverse-proxy)
8. [Iniciar los Servicios](#8-iniciar-los-servicios)
9. [Verificación Post-Instalación](#9-verificación-post-instalación)
10. [Actualizar desde GitHub](#10-actualizar-desde-github)
11. [Comandos de Mantenimiento](#11-comandos-de-mantenimiento)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. Resumen de la Plataforma

AInstein es un sistema enterprise de generación inteligente de Epicrisis Clínicas (EPC) con IA.

### Stack Tecnológico Completo

```
┌───────────────────────────────────────────────────────────────────────────┐
│                     AInstein Platform v3.0.0                              │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│   FRONTEND                    BACKEND                  INFRA              │
│   ─────────                   ───────                  ─────              │
│   React 18.3                  Python 3.12 / FastAPI    Docker             │
│   Vite 5.4                    Rust Engine (FFI)        Nginx              │
│   TypeScript 5.6              Alembic (migrations)     Ubuntu 24          │
│   React Router 6.30           LangChain                                   │
│   Axios                       Google Gemini 2.0                           │
│                                                                           │
│   BASES DE DATOS (Docker)                                                 │
│   ──────────────────────                                                  │
│   PostgreSQL 16    →  Datos ACID, pacientes, EPCs, usuarios               │
│   MongoDB 7        →  HCE raw data, feedback, golden rules, logs         │
│   Redis 7          →  Cache, sesiones, rate limiting                      │
│   Qdrant           →  Vectores, embeddings, RAG                          │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
```

### Repositorios GitHub

| Repositorio | URL |
|---|---|
| **Backend** | `https://github.com/zeron-team/ainstein_be.git` |
| **Frontend** | `https://github.com/zeron-team/ainstein_fe.git` |

---

## 2. Requisitos del Servidor

### Hardware Mínimo

| Recurso | Mínimo | Recomendado |
|---------|--------|-------------|
| **CPU** | 2 cores | 4+ cores |
| **RAM** | 8 GB | 16 GB |
| **Disco** | 50 GB SSD | 100+ GB SSD |
| **Red** | Puerto 80/443 abiertos | IP pública fija |

### Software Base

| Software | Versión Mínima |
|----------|---------------|
| Ubuntu | 22.04 LTS o superior |
| Docker | 24.0+ |
| Docker Compose | 2.20+ |
| Python | 3.11+ |
| Node.js | 18.0+ |
| Nginx | 1.18+ |
| Git | 2.30+ |
| Rust | 1.70+ (para compilar engine) |

---

## 3. Preparar el Servidor

### 3.1 Actualizar el sistema operativo

```bash
sudo apt update && sudo apt upgrade -y
```

### 3.2 Instalar herramientas básicas

```bash
sudo apt install -y \
    curl \
    wget \
    git \
    build-essential \
    software-properties-common \
    ca-certificates \
    gnupg \
    lsb-release \
    jq \
    unzip
```

### 3.3 Verificar versiones

```bash
echo "=== Verificando sistema ==="
lsb_release -d
git --version
```

---

## 4. Instalar Docker y Contenedores

### 4.1 Instalar Docker

```bash
# Instalar Docker Engine
curl -fsSL https://get.docker.com | sudo sh

# Agregar tu usuario al grupo docker (evitar sudo)
sudo usermod -aG docker $USER

# Aplicar cambio de grupo (o cerrar sesión y volver a entrar)
newgrp docker

# Verificar
docker --version
docker compose version
```

### 4.2 Crear directorio del proyecto

```bash
mkdir -p ~/aistein
cd ~/aistein
```

### 4.3 Clonar el repositorio del Backend (contiene docker-compose)

```bash
git clone https://github.com/zeron-team/ainstein_be.git backend
cd backend
```

### 4.4 Configurar variables de Docker

```bash
# Crear archivo de secretos para Docker
cat > .env.docker << 'EOF'
POSTGRES_PASSWORD=ainstein_secure_2026
MONGO_ROOT_PASSWORD=mongo_secure_2026
EOF
```

> ⚠️ **IMPORTANTE**: Cambia estas contraseñas por valores seguros en producción.

### 4.5 Levantar contenedores de base de datos

**Opción A — Usar docker-compose.prod.yml (producción, red interna):**

```bash
docker compose -f docker-compose.prod.yml up -d postgres redis mongo qdrant
```

**Opción B — Levantar cada contenedor individualmente (desarrollo, puertos expuestos):**

```bash
# PostgreSQL 16
docker run -d \
    --name postgres \
    -e POSTGRES_DB=ainstein \
    -e POSTGRES_USER=ainstein \
    -e POSTGRES_PASSWORD=ainstein_secure_2026 \
    -p 5432:5432 \
    -v pg_data:/var/lib/postgresql/data \
    --restart unless-stopped \
    postgres:16-alpine

# MongoDB 7
docker run -d \
    --name mongodb \
    -e MONGO_INITDB_ROOT_USERNAME=admin \
    -e MONGO_INITDB_ROOT_PASSWORD=mongo_secure_2026 \
    -p 27017:27017 \
    -v mongo_data:/data/db \
    --restart unless-stopped \
    mongo:7

# Redis 7
docker run -d \
    --name redis \
    -p 6379:6379 \
    -v redis_data:/data \
    --restart unless-stopped \
    redis:7-alpine \
    redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy volatile-lru

# Qdrant (Vector Database)
docker run -d \
    --name qdrant \
    -p 6333:6333 \
    -p 6334:6334 \
    -v qdrant_data:/qdrant/storage \
    --restart unless-stopped \
    qdrant/qdrant:latest
```

### 4.6 Verificar contenedores

```bash
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"
```

**Resultado esperado:**

```
NAMES       IMAGE               STATUS          PORTS
postgres    postgres:16-alpine  Up X minutes    0.0.0.0:5432->5432/tcp
mongodb     mongo:7             Up X minutes    0.0.0.0:27017->27017/tcp
redis       redis:7-alpine      Up X minutes    0.0.0.0:6379->6379/tcp
qdrant      qdrant/qdrant       Up X minutes    0.0.0.0:6333-6334->6333-6334/tcp
```

### 4.7 Verificar conexiones a las bases de datos

```bash
# PostgreSQL
docker exec postgres pg_isready -U ainstein -d ainstein
# Esperado: /var/run/postgresql:5432 - accepting connections

# MongoDB
docker exec mongodb mongosh --quiet --eval "db.adminCommand('ping').ok"
# Esperado: 1

# Redis
docker exec redis redis-cli ping
# Esperado: PONG
```

---

## 5. Instalar y Configurar el Backend

### 5.1 Instalar Python 3.12

```bash
# Ubuntu 24 ya incluye Python 3.12
python3 --version

# Si no está instalado:
sudo apt install -y python3 python3-venv python3-pip python3-dev
```

### 5.2 Crear entorno virtual

```bash
cd ~/aistein/backend

# Crear venv
python3 -m venv .venv

# Activar
source .venv/bin/activate

# Actualizar pip
pip install --upgrade pip wheel setuptools
```

### 5.3 Instalar dependencias Python

```bash
pip install -r requirements.txt
```

### 5.4 Compilar Motor Rust (ainstein_core)

```bash
# Instalar Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
source $HOME/.cargo/env

# Instalar maturin (puente Python-Rust)
pip install maturin

# Compilar el módulo
cd rust_lib
maturin develop --release
cd ..

# Verificar
python -c "import ainstein_core; print('✅ Rust engine OK')"
```

### 5.5 Configurar variables de entorno (.env)

```bash
cat > .env << 'ENVEOF'
# ═══════════════════════════════════════════════════════════════════
#               AInstein Backend - Configuración
# ═══════════════════════════════════════════════════════════════════

# ─── PostgreSQL ───
SQL_URL=postgresql://ainstein:ainstein_secure_2026@localhost:5432/ainstein

# ─── MongoDB ───
MONGO_URL=mongodb://admin:mongo_secure_2026@localhost:27017/ainstein?authSource=admin

# ─── Redis ───
REDIS_URL=redis://localhost:6379/0

# ─── JWT Security ───
JWT_SECRET=CAMBIAR_POR_CLAVE_SEGURA_DE_MINIMO_32_CARACTERES
JWT_EXPIRE_MINUTES=60

# ─── Google Gemini API (LLM) ───
GEMINI_API_KEY=tu_api_key_de_google_gemini
GEMINI_MODEL=gemini-2.0-flash
GEMINI_API_HOST=https://generativelanguage.googleapis.com
GEMINI_API_VERSION=v1beta

# ─── CORS (agregar URL de tu servidor) ───
CORS_ORIGINS=["http://localhost:5173","http://TU_IP_SERVIDOR","https://tu-dominio.com"]

# ─── HCE Upload ───
HCE_UPLOAD_DIR=/tmp/hce_uploads

# ─── Markey/AInstein Integration (WebService externo) ───
AINSTEIN_HTTP_METHOD=GET
AINSTEIN_API_URL=https://ainstein1.markeyoci.com.ar/obtener
AINSTEIN_APP=AInstein
AINSTEIN_API_KEY=tu_api_key_markey
AINSTEIN_TOKEN=tu_token_markey
AINSTEIN_TIMEOUT_SECONDS=60

# ─── Qdrant (Vector Database voor RAG) ───
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_ENABLED=true
ENVEOF
```

> ⚠️ **IMPORTANTE**: 
> - Reemplaza `JWT_SECRET` con una clave segura real
> - Reemplaza `GEMINI_API_KEY` con tu API key de Google AI Studio
> - Reemplaza `TU_IP_SERVIDOR` con la IP real de tu servidor
> - Reemplaza las credenciales de Markey si aplica

### 5.6 Ejecutar migraciones de PostgreSQL

```bash
source .venv/bin/activate

# Ejecutar todas las migraciones
PYTHONPATH=. alembic upgrade head

# Verificar estado
PYTHONPATH=. alembic current
```

**Resultado esperado:**
```
INFO  [alembic.runtime.migration] Running upgrade  -> b326df34e12a, initial postgres schema
INFO  [alembic.runtime.migration] Running upgrade b326df34e12a -> 82c4908f8ccc, add multitenancy tables
...
```

### 5.7 Crear Tenant y Usuario Admin

```bash
# Crear tenant por defecto (markey)
PYTHONPATH=. python scripts/seed_default_tenant.py

# Migrar configuración HCE al tenant
PYTHONPATH=. python scripts/migrate_markey_to_tenant.py

# Crear usuario administrador
PYTHONPATH=. python create_admin_user.py
```

> 📝 El script `create_admin_user.py` te pedirá email, nombre y contraseña del admin.

### 5.8 Verificar que el Backend arranca

```bash
# Iniciar temporalmente para verificar
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# Esperar 3 segundos
sleep 3

# Verificar
curl http://localhost:8000/
# Esperado: {"ok": true, "service": "EPC Suite"}

# Detener
kill %1
```

---

## 6. Instalar y Configurar el Frontend

### 6.1 Instalar Node.js 20

```bash
# Instalar NVM (Node Version Manager)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.bashrc

# Instalar Node.js 20 LTS
nvm install 20
nvm use 20
nvm alias default 20

# Verificar
node --version   # v20.x.x
npm --version    # 10.x.x
```

### 6.2 Clonar el repositorio

```bash
cd ~/aistein
git clone https://github.com/zeron-team/ainstein_fe.git frontend
cd frontend
```

### 6.3 Instalar dependencias

```bash
npm install
```

### 6.4 Configurar variables de entorno

**Para desarrollo local:**
```bash
echo "VITE_API_URL=http://localhost:8000" > .env
```

**Para producción (con Nginx proxy):**
```bash
# Cuando Nginx hace proxy de /api/ → backend:8000/
# El frontend usa la misma URL del servidor
echo "VITE_API_URL=https://tu-dominio.com" > .env
```

> 💡 Si usas Nginx como proxy inverso, `VITE_API_URL` debe apuntar al mismo dominio/IP, y Nginx redirige `/api/` al backend.

### 6.5 Compilar para producción

```bash
npm run build
```

**Resultado esperado:**
```
✓ built in 7.xx s
dist/index.html    →  XX KB
dist/assets/...    →  XXX KB
```

### 6.6 Crear directorio de despliegue

```bash
sudo mkdir -p /var/www/html/aistein-frontend
sudo cp -r dist/* /var/www/html/aistein-frontend/
```

---

## 7. Configurar Nginx (Reverse Proxy)

### 7.1 Instalar Nginx

```bash
sudo apt install -y nginx
sudo systemctl enable nginx
sudo systemctl start nginx
```

### 7.2 Crear configuración del sitio

```bash
sudo tee /etc/nginx/sites-available/ainstein << 'NGINX_EOF'
server {
    listen 80 default_server;
    listen [::]:80 default_server;

    # Tamaño máximo de upload (para HCE JSON)
    client_max_body_size 50M;

    server_name _;

    # ══════════════════════════════════════════════════════════
    # FRONTEND (React SPA)
    # ══════════════════════════════════════════════════════════
    root /var/www/html/aistein-frontend;
    index index.html;

    # index.html SIEMPRE sin cache (para que tome el nuevo hash del JS/CSS)
    location = /index.html {
        add_header Cache-Control "no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0" always;
    }

    # Assets con hash de Vite: cache largo e inmutable
    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable" always;
        try_files $uri =404;
    }

    # SPA: todas las rutas van a index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # ══════════════════════════════════════════════════════════
    # BACKEND API (FastAPI via reverse proxy)
    # ══════════════════════════════════════════════════════════
    location /api/ {
        # La barra final hace que /api/auth/login → /auth/login en el backend
        proxy_pass http://127.0.0.1:8000/;

        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Desactivar buffering para SSE (Server-Sent Events)
        proxy_buffering off;
    }

    # ══════════════════════════════════════════════════════════
    # SECURITY HEADERS
    # ══════════════════════════════════════════════════════════
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
NGINX_EOF
```

### 7.3 Activar el sitio

```bash
# Desactivar sitio default si existe
sudo rm -f /etc/nginx/sites-enabled/default

# Activar ainstein
sudo ln -sf /etc/nginx/sites-available/ainstein /etc/nginx/sites-enabled/ainstein

# Verificar sintaxis
sudo nginx -t

# Recargar Nginx
sudo systemctl reload nginx
```

### 7.4 (Opcional) Configurar HTTPS con Let's Encrypt

```bash
# Instalar Certbot
sudo apt install -y certbot python3-certbot-nginx

# Obtener certificado SSL (reemplazar con tu dominio real)
sudo certbot --nginx -d tu-dominio.com -d www.tu-dominio.com

# Auto-renovación (se configura automáticamente)
sudo certbot renew --dry-run
```

---

## 8. Iniciar los Servicios

### 8.1 Iniciar el Backend

**Opción A — Proceso en background (desarrollo/testing):**

```bash
cd ~/aistein/backend
source .venv/bin/activate
nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/backend.log 2>&1 &
echo "Backend PID: $!"
```

**Opción B — Systemd service (producción, se reinicia solo):**

```bash
# Crear archivo de servicio
sudo tee /etc/systemd/system/ainstein-backend.service << 'SERVICE_EOF'
[Unit]
Description=AInstein Backend API
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/aistein/backend
Environment=PATH=/home/ubuntu/aistein/backend/.venv/bin:/usr/local/bin:/usr/bin
ExecStart=/home/ubuntu/aistein/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE_EOF

# Activar y arrancar
sudo systemctl daemon-reload
sudo systemctl enable ainstein-backend
sudo systemctl start ainstein-backend

# Verificar
sudo systemctl status ainstein-backend
```

### 8.2 Verificar todos los servicios

```bash
echo "=== Docker Containers ==="
docker ps --format "table {{.Names}}\t{{.Status}}"

echo ""
echo "=== Backend API ==="
curl -s http://localhost:8000/ | jq .

echo ""
echo "=== Frontend (Nginx) ==="
curl -s -o /dev/null -w "HTTP %{http_code}" http://localhost/
```

---

## 9. Verificación Post-Instalación

### 9.1 Checklist rápido

```bash
# 1. Docker containers corriendo
docker ps --format "{{.Names}}: {{.Status}}" | grep -E "postgres|mongodb|redis|qdrant"

# 2. Backend responde
curl -s http://localhost:8000/ | jq .ok
# Esperado: true

# 3. Frontend carga
curl -s -o /dev/null -w "%{http_code}" http://localhost/
# Esperado: 200

# 4. Rust engine
cd ~/aistein/backend
source .venv/bin/activate
python -c "import ainstein_core; print('✅ Rust OK')"
```

### 9.2 Login de prueba

```bash
# Login con admin
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"admin@example.com","password":"tu_password_admin"}' | jq -r '.access_token')

echo "Token: ${TOKEN:0:20}..."

# Verificar health check completo
curl -s http://localhost:8000/admin/health \
    -H "Authorization: Bearer $TOKEN" | jq .
```

**Resultado esperado del health check:**
```json
{
  "status": "healthy",
  "services": {
    "docker":      { "status": "ok" },
    "postgres":    { "status": "ok" },
    "redis":       { "status": "ok" },
    "mongodb":     { "status": "ok" },
    "qdrant":      { "status": "ok" },
    "rust_core":   { "status": "ok" },
    "gemini_api":  { "status": "ok" },
    "ainstein_ws": { "status": "ok" },
    "langchain":   { "status": "ok" }
  }
}
```

### 9.3 Verificar Golden Rules

```bash
# Verificar que las reglas de oro se cargaron
curl -s http://localhost:8000/admin/golden-rules \
    -H "Authorization: Bearer $TOKEN" | jq '.[].key'
# Esperado: "motivo", "evolucion", "procedimientos", "interconsultas", "medicacion", "obito", "pdf"
```

---

## 10. Actualizar desde GitHub

### 10.1 Actualizar Backend

```bash
cd ~/aistein/backend

# Bajar cambios
git pull origin main

# Activar entorno
source .venv/bin/activate

# Instalar nuevas dependencias (si las hay)
pip install -r requirements.txt

# Ejecutar migraciones (si las hay)
PYTHONPATH=. alembic upgrade head

# Reiniciar backend
sudo systemctl restart ainstein-backend
# O si usas nohup:
kill $(pgrep -f "uvicorn app.main:app")
sleep 2
nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/backend.log 2>&1 &
```

### 10.2 Actualizar Frontend

```bash
cd ~/aistein/frontend

# Bajar cambios
git pull origin main

# Instalar nuevas dependencias (si las hay)
npm install

# Compilar
npm run build

# Desplegar
sudo cp -r dist/* /var/www/html/aistein-frontend/
sudo nginx -s reload
```

---

## 11. Comandos de Mantenimiento

### 11.1 Docker

```bash
# Ver estado de contenedores
docker ps

# Ver logs de un contenedor
docker logs -f mongodb --tail 50

# Reiniciar un contenedor
docker restart postgres

# Detener todo
docker stop postgres mongodb redis qdrant

# Iniciar todo
docker start postgres mongodb redis qdrant
```

### 11.2 Backups

```bash
# ── PostgreSQL ──
docker exec postgres pg_dump -U ainstein ainstein > backup_postgres_$(date +%Y%m%d).sql

# ── MongoDB ──
docker exec mongodb mongodump --username admin --password mongo_secure_2026 --authenticationDatabase admin --out /tmp/mongodump
docker cp mongodb:/tmp/mongodump ./backup_mongo_$(date +%Y%m%d)

# ── Restaurar PostgreSQL ──
docker exec -i postgres psql -U ainstein ainstein < backup_postgres_20260227.sql

# ── Restaurar MongoDB ──
docker cp ./backup_mongo_20260227 mongodb:/tmp/mongodump
docker exec mongodb mongorestore --username admin --password mongo_secure_2026 --authenticationDatabase admin /tmp/mongodump
```

### 11.3 Base de datos

```bash
# Conectar a PostgreSQL interactivo
docker exec -it postgres psql -U ainstein -d ainstein

# Conectar a MongoDB interactivo
docker exec -it mongodb mongosh -u admin -p mongo_secure_2026 --authenticationDatabase admin

# Ver migraciones pendientes
cd ~/aistein/backend && source .venv/bin/activate
PYTHONPATH=. alembic current
PYTHONPATH=. alembic history
```

### 11.4 Logs

```bash
# Backend logs
tail -f /tmp/backend.log
# o con systemd:
sudo journalctl -u ainstein-backend -f --no-pager

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

---

## 12. Troubleshooting

### Errores Comunes

| Problema | Causa | Solución |
|----------|-------|----------|
| **`Connection refused` en PostgreSQL** | Container no está corriendo | `docker start postgres` |
| **`Connection refused` en MongoDB** | Container no está corriendo | `docker start mongodb` |
| **`ModuleNotFoundError: ainstein_core`** | Motor Rust no compilado | `cd rust_lib && maturin develop --release` |
| **`401 Unauthorized`** | Token JWT expirado | Re-loguearse |
| **Página en blanco en frontend** | Build desactualizado | `npm run build && sudo cp -r dist/* /var/www/html/aistein-frontend/` |
| **CORS error** | URL no en CORS_ORIGINS | Agregar URL a `CORS_ORIGINS` en `.env` y reiniciar backend |
| **`Tenant 'X' no tiene endpoint`** | Falta migración | `PYTHONPATH=. python scripts/migrate_markey_to_tenant.py` |
| **Migraciones fallan** | Falta PYTHONPATH | Siempre usar `PYTHONPATH=. alembic ...` |
| **Nginx 502 Bad Gateway** | Backend no está corriendo | Verificar: `curl http://localhost:8000/` |
| **Gemini API error** | API Key inválida | Verificar `GEMINI_API_KEY` en `.env` |
| **`npm install` falla** | Versión de Node incompatible | `nvm install 20 && nvm use 20` |
| **Puertos en uso** | Otro proceso usa el puerto | `sudo lsof -i :8000` y matar proceso |

### Verificación Rápida de Todo

```bash
#!/bin/bash
echo "═══════════════════════════════════════════════"
echo "   AInstein — Verificación del Sistema"
echo "═══════════════════════════════════════════════"

echo ""
echo "1. Docker containers:"
for c in postgres mongodb redis qdrant; do
    STATUS=$(docker inspect -f '{{.State.Status}}' $c 2>/dev/null || echo "not found")
    if [ "$STATUS" = "running" ]; then
        echo "   ✅ $c: running"
    else
        echo "   ❌ $c: $STATUS"
    fi
done

echo ""
echo "2. Backend API:"
RESP=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ 2>/dev/null)
if [ "$RESP" = "200" ]; then
    echo "   ✅ API: respondiendo (HTTP $RESP)"
else
    echo "   ❌ API: error (HTTP $RESP)"
fi

echo ""
echo "3. Frontend (Nginx):"
RESP=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/ 2>/dev/null)
if [ "$RESP" = "200" ]; then
    echo "   ✅ Frontend: respondiendo (HTTP $RESP)"
else
    echo "   ❌ Frontend: error (HTTP $RESP)"
fi

echo ""
echo "4. Nginx:"
sudo nginx -t 2>&1 | grep -q "successful" && echo "   ✅ Config OK" || echo "   ❌ Config error"

echo ""
echo "═══════════════════════════════════════════════"
```

---

## 📊 Diagrama de Arquitectura Completa

```
                    ┌──────────────────┐
                    │     Internet     │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │   Nginx (:80)    │
                    │   Reverse Proxy  │
                    └───┬──────────┬───┘
                        │          │
              ┌─────────▼──┐  ┌───▼──────────┐
              │  Frontend  │  │  /api/ proxy  │
              │  React SPA │  │              │
              │  /var/www/ │  └──────┬───────┘
              └────────────┘         │
                            ┌────────▼─────────┐
                            │  Backend FastAPI  │
                            │  (:8000)          │
                            └───┬──┬──┬──┬─────┘
                                │  │  │  │
           ┌────────────────────┘  │  │  └──────────────────┐
           │                       │  │                     │
    ┌──────▼──────┐  ┌────────────▼──▼─────────┐  ┌───────▼────────┐
    │ PostgreSQL  │  │  MongoDB    │  Redis     │  │     Qdrant     │
    │ (:5432)     │  │  (:27017)   │  (:6379)   │  │  (:6333)       │
    │ ACID + RLS  │  │  HCE/Logs   │  Cache     │  │  Vectors/RAG   │
    └─────────────┘  └────────────────┘──────────┘  └────────────────┘

    ┌────────────────────────────────────────────────────────────────┐
    │                    Servicios Externos                          │
    │  Google Gemini AI (LLM)  │  Markey HCE WebService             │
    └────────────────────────────────────────────────────────────────┘
```

---

## 📄 Licencia

Propiedad de **Zeron Team** - Todos los derechos reservados.

---

*Documento creado: 2026-02-27 | AInstein Platform v3.0.0*
