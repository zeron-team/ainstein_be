# 🔍 Checklist de Verificación del Sistema AInstein

> **Objetivo**: Verificar que TODOS los componentes del sistema estén funcionando correctamente después de cualquier modificación o despliegue.

---

## 📋 Resumen Rápido de Checks

| Categoría | Check | Comando/Verificación |
|-----------|-------|---------------------|
| 🐳 Docker | Containers | `docker ps` |
| 🐘 PostgreSQL | Conexión | Health Check API |
| 🔴 Redis | Conexión | Health Check API |
| 🍃 MongoDB | Conexión | Health Check API |
| 🔷 Qdrant | Conexión | Health Check API |
| ⚙️ Rust Core | Motor | Health Check API |
| 🤖 Gemini API | LLM | Health Check API |
| 🏥 HCE WS | WebService Externo | Health Check API |
| 📜 LangChain | RAG | Health Check API |
| 🔐 Auth | JWT/Tokens | Manual |
| 👥 Tenants | Configuración Multi-tenant | Admin Panel |

---

## 1. 🐳 Infraestructura Docker

### 1.1 Verificar que Docker está corriendo
```bash
docker info
```

### 1.2 Verificar containers FERRO Stack
```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

**Containers esperados:**
- [ ] `ferro_postgres` - Up (PostgreSQL 15)
- [ ] `ferro_redis` - Up (Redis 7)
- [ ] `ferro_mongo` - Up (MongoDB 7)
- [ ] `ferro_qdrant` - Up (Qdrant vector DB)

### 1.3 Si algún container no está corriendo
```bash
cd /home/ubuntu/ainstein/ainstein_be
docker-compose -f docker-compose.prod.yml up -d
```

---

## 2. 🐘 PostgreSQL (Relational Core)

### 2.1 Verificar conexión directa
```bash
docker exec ferro_postgres pg_isready -U ainstein
```
**Esperado:** `accepting connections`

### 2.2 Verificar credenciales en `.env`
```bash
grep SQL_URL /home/ubuntu/ainstein/ainstein_be/.env
```
**Variables requeridas:**
- [ ] `SQL_URL` - URL de conexión con usuario/password correcto

### 2.3 Verificar que las migraciones están aplicadas
```bash
cd /home/ubuntu/ainstein/ainstein_be
source .venv/bin/activate
PYTHONPATH=. alembic current
```

---

## 3. 🔴 Redis (Dopamine Layer - Cache)

### 3.1 Verificar conexión directa
```bash
docker exec ferro_redis redis-cli ping
```
**Esperado:** `PONG`

### 3.2 Verificar variable `.env`
```bash
grep REDIS_URL /home/ubuntu/ainstein/ainstein_be/.env
```
**Variables requeridas:**
- [ ] `REDIS_URL` - Formato: `redis://localhost:6379/0`

---

## 4. 🍃 MongoDB (Flexible Store)

### 4.1 Verificar conexión directa
```bash
docker exec ferro_mongo mongosh --eval "db.adminCommand('ping')"
```
**Esperado:** `{ ok: 1 }`

### 4.2 Verificar variables `.env`
```bash
grep MONGO /home/ubuntu/ainstein/ainstein_be/.env
```
**Variables requeridas:**
- [ ] `MONGO_URL` - URL con credenciales
- [ ] `MONGO_DB_NAME` - Nombre de la base de datos

### 4.3 Verificar colecciones principales
```bash
docker exec ferro_mongo mongosh ainstein_db --eval "db.getCollectionNames()"
```
**Colecciones esperadas:** `hce_data`, `feedback`, `llm_usage`, `clinical_case_library`

---

## 5. 🔷 Qdrant (Vector Brain - RAG)

### 5.1 Verificar conexión directa
```bash
curl http://localhost:6333/healthz
```
**Esperado:** `OK` o respuesta JSON

### 5.2 Verificar variables `.env`
```bash
grep QDRANT /home/ubuntu/ainstein/ainstein_be/.env
```
**Variables requeridas:**
- [ ] `QDRANT_HOST` - Default: `localhost`
- [ ] `QDRANT_PORT` - Default: `6333`
- [ ] `QDRANT_ENABLED` - Default: `true`

### 5.3 Verificar colecciones
```bash
curl http://localhost:6333/collections
```

---

## 6. ⚙️ Rust Core Engine (ainstein_core)

### 6.1 Verificar que el módulo está compilado e instalado
```bash
cd /home/ubuntu/ainstein/ainstein_be
source .venv/bin/activate
python -c "import ainstein_core; print('Rust Core OK:', ainstein_core.chunk_text('test', 10))"
```
**Esperado:** `Rust Core OK: ['test']`

### 6.2 Si falla, recompilar
```bash
cd /home/ubuntu/ainstein/ainstein_be/rust_lib
maturin develop --release
```

---

## 7. 🤖 Gemini API (LLM Provider)

### 7.1 Verificar variables `.env`
```bash
grep GEMINI /home/ubuntu/ainstein/ainstein_be/.env
```
**Variables requeridas:**
- [ ] `GEMINI_API_KEY` - API Key válida de Google AI
- [ ] `GEMINI_MODEL` - Default: `gemini-2.0-flash`
- [ ] `GEMINI_API_HOST` - Default: `https://generativelanguage.googleapis.com`
- [ ] `GEMINI_API_VERSION` - Default: `v1beta`

### 7.2 Verificar conectividad API
```bash
cd /home/ubuntu/ainstein/ainstein_be
source .venv/bin/activate
PYTHONPATH=. python -c "
from app.core.config import settings
import httpx
url = f'{settings.GEMINI_API_HOST}/{settings.GEMINI_API_VERSION}/models'
resp = httpx.get(url, params={'key': settings.GEMINI_API_KEY})
print(f'Status: {resp.status_code}')
if resp.status_code == 200:
    models = resp.json().get('models', [])
    print(f'Modelos disponibles: {len(models)}')
else:
    print(f'Error: {resp.text[:200]}')
"
```

---

## 8. 🏥 HCE WebService (Markey / Integración Externa)

> ⚠️ **CRÍTICO**: Este fue el origen del error "Tenant 'markey' no tiene endpoint externo configurado"

### 8.1 Verificar variables `.env` (valores por defecto)
```bash
grep AINSTEIN /home/ubuntu/ainstein/ainstein_be/.env
```
**Variables requeridas:**
- [ ] `AINSTEIN_API_URL` - URL del WebService HCE
- [ ] `AINSTEIN_APP` - Nombre de la aplicación (ej: `AInstein`)
- [ ] `AINSTEIN_API_KEY` - API Key del proveedor
- [ ] `AINSTEIN_TOKEN` - Token de autenticación
- [ ] `AINSTEIN_HTTP_METHOD` - Método HTTP (GET/POST)
- [ ] `AINSTEIN_TIMEOUT_SECONDS` - Timeout en segundos

### 8.2 ⚠️ MIGRAR configuración a la base de datos del Tenant
```bash
cd /home/ubuntu/ainstein/ainstein_be
source .venv/bin/activate
PYTHONPATH=. python scripts/migrate_markey_to_tenant.py
```

### 8.3 Verificar configuración del Tenant en BD
```bash
cd /home/ubuntu/ainstein/ainstein_be
source .venv/bin/activate
PYTHONPATH=. python -c "
from app.db.session import SessionLocal
from app.domain.models import Tenant
db = SessionLocal()
t = db.query(Tenant).filter(Tenant.code == 'markey').first()
if t:
    print('✅ Tenant markey:')
    print(f'   is_active: {t.is_active}')
    print(f'   integration_type: {t.integration_type}')
    print(f'   external_endpoint: {t.external_endpoint[:50] if t.external_endpoint else \"❌ NO CONFIGURADO\"}...')
    print(f'   external_token: {\"✅ Configurado\" if t.external_token else \"❌ NO CONFIGURADO\"}')
    print(f'   external_headers: {\"✅ Configurado\" if t.external_headers else \"❌ NO CONFIGURADO\"}')
else:
    print('❌ Tenant markey NO encontrado')
db.close()
"
```

### 8.4 Probar conexión al HCE vía API
```bash
curl -X GET "http://localhost:8000/api/tenants/{TENANT_ID}/test-connection" \
  -H "Authorization: Bearer {TOKEN}"
```
O desde el Admin Panel → Tenants → Test Connection

---

## 9. 🔐 Autenticación y Seguridad

### 9.1 Verificar variables JWT en `.env`
```bash
grep JWT /home/ubuntu/ainstein/ainstein_be/.env
```
**Variables requeridas:**
- [ ] `JWT_SECRET` - Secreto para firmar tokens (mínimo 32 caracteres)
- [ ] `JWT_EXPIRE_MINUTES` - Tiempo de expiración (default: 60)

### 9.2 Verificar usuario admin existe
```bash
cd /home/ubuntu/ainstein/ainstein_be
source .venv/bin/activate
PYTHONPATH=. python -c "
from app.db.session import SessionLocal
from app.domain.models import User
db = SessionLocal()
admins = db.query(User).filter(User.role == 'admin').all()
print(f'Usuarios admin encontrados: {len(admins)}')
for a in admins:
    print(f'  - {a.email} (tenant: {a.tenant_id})')
db.close()
"
```

### 9.3 Si no hay admin, crear uno
```bash
cd /home/ubuntu/ainstein/ainstein_be
source .venv/bin/activate
PYTHONPATH=. python create_admin_user.py
```

---

## 10. 🖥️ Backend FastAPI

### 10.1 Verificar que el servidor está corriendo
```bash
curl http://localhost:8000/docs
```

### 10.2 Si no está corriendo, iniciar
```bash
cd /home/ubuntu/ainstein/ainstein_be
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 10.3 Verificar Health Check completo
```bash
# Primero obtener un token de autenticación
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"your_password"}' | jq -r '.access_token')

# Luego hacer el health check
curl -s http://localhost:8000/api/admin/health \
  -H "Authorization: Bearer $TOKEN" | jq
```

---

## 11. 🎨 Frontend React

### 11.1 Verificar que el servidor de desarrollo está corriendo
```bash
curl http://localhost:5173
```

### 11.2 Si no está corriendo, iniciar
```bash
cd /home/ubuntu/ainstein/ainstein_fe
npm run dev
```

### 11.3 Verificar conexión al backend
- [ ] Abrir http://localhost:5173 en navegador
- [ ] Verificar que la página de login carga
- [ ] Verificar que no hay errores de CORS en la consola

---

## 12. 🌐 Nginx (Producción)

### 12.1 Verificar estado de Nginx
```bash
sudo systemctl status nginx
```

### 12.2 Verificar configuración del sitio
```bash
sudo nginx -t
```

### 12.3 Verificar SSL/HTTPS
- [ ] Certificados Let's Encrypt válidos
- [ ] Redirección HTTP → HTTPS funciona

---

## 13. 📜 RAG y LangChain

### 13.1 Verificar configuración en `.env`
```bash
grep RAG /home/ubuntu/ainstein/ainstein_be/.env
```
**Variables requeridas:**
- [ ] `RAG_ENABLED` - Default: `true`
- [ ] `RAG_FEW_SHOT_EXAMPLES` - Default: `3`

### 13.2 Verificar LangChain disponible
```bash
cd /home/ubuntu/ainstein/ainstein_be
source .venv/bin/activate
python -c "from langchain_google_genai import ChatGoogleGenerativeAI; print('LangChain OK')"
```

---

## 14. 🧪 Test de Flujo Completo

### 14.1 Login
- [ ] Ir a http://localhost:5173/login
- [ ] Ingresar credenciales de admin
- [ ] Verificar redirección al dashboard

### 14.2 Health Check desde Admin Panel
- [ ] Ir a Admin → Health Check
- [ ] Verificar que todos los servicios muestran ✅

### 14.3 Listar Pacientes
- [ ] Ir a Pacientes
- [ ] Verificar que la lista carga correctamente

### 14.4 Generar EPC
- [ ] Seleccionar un paciente con internación
- [ ] Generar epicrisis
- [ ] Verificar que se genera sin errores

### 14.5 Consultar HCE WS (WebService Externo)
- [ ] Ir a Admin → Tenants → Markey
- [ ] Test Connection → Debe mostrar ✅

---

## 15. 🚨 Troubleshooting Rápido

### Error: "Tenant 'X' no tiene endpoint externo configurado"
```bash
# Ejecutar migración de configuración
cd /home/ubuntu/ainstein/ainstein_be
PYTHONPATH=. python scripts/migrate_markey_to_tenant.py
```

### Error: Conexión a base de datos rechazada
```bash
# Verificar containers
docker ps
# Reiniciar containers si es necesario
docker-compose -f docker-compose.prod.yml restart
```

### Error: Module 'ainstein_core' not found
```bash
cd /home/ubuntu/ainstein/ainstein_be/rust_lib
source ../.venv/bin/activate
maturin develop --release
```

### Error: 401 Unauthorized en API
```bash
# Verificar que las credenciales son correctas
# Verificar que el JWT_SECRET no cambió
# Re-loguear para obtener nuevo token
```

### Error: CORS en frontend
```bash
# Verificar CORS_ORIGINS en .env incluye la URL del frontend
grep CORS /home/ubuntu/ainstein/ainstein_be/.env
```

---

## 📝 Checklist Pre-Deploy

Antes de cualquier modificación o deploy, verificar:

- [ ] **Backup de BD**: `pg_dump` de PostgreSQL
- [ ] **Backup de MongoDB**: `mongodump`
- [ ] **Git status limpio**: No hay cambios sin commitear
- [ ] **Tests pasan**: `pytest` sin errores
- [ ] **Variables .env completas**: Todas las variables requeridas
- [ ] **Tenant migrado**: Script `migrate_markey_to_tenant.py` ejecutado

---

## 📝 Checklist Post-Deploy

Después de cualquier modificación o deploy:

- [ ] Health Check API: Todos los servicios ✅
- [ ] Login funciona
- [ ] Lista pacientes carga
- [ ] Generación EPC funciona
- [ ] Test conexión HCE ✅
- [ ] No errores en logs: `tail -f backend.log`

---

**Última actualización**: 2026-02-03
**Versión**: 1.0
