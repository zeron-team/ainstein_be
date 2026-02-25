# 📦 Database Dumps — AInstein FERRO D2 v3.0.0

> **Fecha de generación**: 2026-02-25 18:07 UTC  
> **Servidor fuente**: vps-c87d687c.vps.ovh.ca

---

## 📋 Resumen de Archivos

| Archivo | Base de Datos | Formato | Tamaño | Descripción |
|---------|---------------|---------|--------|-------------|
| `postgres_ainstein.dump` | PostgreSQL 16 | Custom (pg_dump) | 28 MB | Dump binario, restauración selectiva |
| `postgres_ainstein.sql` | PostgreSQL 16 | SQL plano | 213 MB | Dump legible, restauración completa |
| `mongo_epc/` | MongoDB 7 | BSON gzipped (mongodump) | ~15 MB | Directorio con todas las colecciones |
| `qdrant_hce_chunks.snapshot` | Qdrant | Snapshot nativo | 58 KB | Colección de vectores HCE |
| `qdrant_epc_feedback.snapshot` | Qdrant | Snapshot nativo | 58 KB | Colección de vectores de feedback |

---

## 🐘 PostgreSQL — `ainstein` (Truth Core ACID)

### Propósito
Base de datos relacional principal. Almacena toda la **verdad del sistema**: pacientes, internaciones, epicrisis, usuarios, tenants, SNOMED CT, políticas ABAC.

### Tablas (28 total)

#### Tablas de Negocio Principal
| Tabla | Filas | Descripción |
|-------|-------|-------------|
| `patients` | 55 | Datos de pacientes (nombre, DNI, código, fecha nacimiento) |
| `admissions` | 94 | Internaciones de pacientes |
| `epc` | 0 | Epicrisis generadas (tabla principal) |
| `epc_events` | 340 | Eventos/historial de acciones sobre EPCs |
| `patient_status` | 55 | Estado actual de cada paciente |

#### Seguridad y Multi-Tenancy
| Tabla | Filas | Descripción |
|-------|-------|-------------|
| `users` | 11 | Usuarios del sistema (médicos, admin) |
| `roles` | 3 | Roles disponibles (admin, doctor, etc.) |
| `tenants` | 1 | Tenants/clínicas configuradas |
| `tenant_api_keys` | 1 | API keys por tenant |
| `abac_policies` | 0 | Políticas de control de acceso (ABAC) |
| `abac_audit_log` | 0 | Log de auditoría de accesos |

#### Configuración
| Tabla | Filas | Descripción |
|-------|-------|-------------|
| `branding` | 1 | Personalización visual por tenant |
| `alembic_version` | 1 | Versión de migraciones aplicadas |

#### SNOMED CT (Terminología Clínica)
| Tabla | Filas | Descripción |
|-------|-------|-------------|
| `snomed_concept` | 55,516 | Conceptos SNOMED CT |
| `snomed_description` | 132,187 | Descripciones de conceptos |
| `snomed_relationship` | 451,291 | Relaciones entre conceptos |
| `snomed_stated_relationship` | 147,696 | Relaciones enunciadas |
| `snomed_concrete_value` | 102,860 | Valores concretos |
| `snomed_refset` | 94,085 | Reference sets |
| `snomed_resource_refset` | 95,958 | Reference sets de recursos |
| `snomed_owl_expression` | 92,639 | Expresiones OWL |
| `snomed_language` | 132,386 | Traducciones por idioma |
| `snomed_medicinal_product` | 19,068 | Productos medicinales |
| `snomed_attribute_value` | 6,951 | Valores de atributos |
| `snomed_association` | 1,820 | Asociaciones entre conceptos |
| `snomed_map_simple` | 499 | Mapeos simples |
| `snomed_map_icd10` | 297 | Mapeos a ICD-10 |
| `snomed_text_definition` | 8 | Definiciones textuales |

### Cómo Importar

#### Opción A: Formato Custom (recomendado — permite restauración selectiva)
```bash
# Crear base de datos (si no existe)
createdb -U ainstein ainstein

# Restaurar completo
pg_restore -U ainstein -d ainstein --clean --if-exists postgres_ainstein.dump

# Restaurar solo una tabla específica
pg_restore -U ainstein -d ainstein -t patients postgres_ainstein.dump
```

#### Opción B: Formato SQL (legible, más lento)
```bash
# Crear base de datos
createdb -U ainstein ainstein

# Restaurar
psql -U ainstein -d ainstein < postgres_ainstein.sql
```

> **Credenciales por defecto**: usuario `ainstein`, password en `.env` → `SQL_URL`

---

## 🍃 MongoDB — `epc` (Flexible Store)

### Propósito
Almacena datos **flexibles y semiestructurados**: historias clínicas externas (HCE raw JSON), feedback de médicos, versiones de EPCs, reglas de aprendizaje, y tracking de uso de LLM.

### Colecciones (10 total)

| Colección | Documentos | Tamaño Comprimido | Descripción |
|-----------|------------|-------------------|-------------|
| `hce_docs` | 157 | 14 MB | Historias clínicas electrónicas (JSON raw del WS externo) |
| `epc_feedback` | 238 | 60 KB | Feedback de médicos sobre EPCs generadas |
| `epc_docs` | 103 | 170 KB | Documentos de epicrisis generadas |
| `epc_versions` | 169 | 231 KB | Versiones históricas de EPCs (versionado) |
| `learning_rules` | 279 | 19 KB | Reglas de aprendizaje generadas por IA |
| `learning_problems` | 175 | 22 KB | Problemas detectados en feedback |
| `learning_events` | 20 | 1.5 KB | Eventos del ciclo de aprendizaje |
| `llm_usage` | 278 | 9.3 KB | Registro de uso de LLM (tokens, costos) |
| `epc_section_corrections` | 14 | 918 B | Correcciones por sección de EPC |
| `chat_history` | 0 | — | Historial de chat (futuro) |
| `epc_logs` | 0 | — | Logs de generación (futuro) |
| `section_mapping_dictionary` | 0 | — | Diccionario de mapeo de secciones (futuro) |

### Cómo Importar

```bash
# Restaurar toda la base 'epc' desde el directorio de dump
mongorestore --uri="mongodb://epc_user:epc_strong_pass_2025@localhost:27017/epc?authSource=epc" \
  --gzip \
  --dir=mongo_epc/ \
  --drop

# Restaurar solo una colección específica
mongorestore --uri="mongodb://epc_user:epc_strong_pass_2025@localhost:27017/epc?authSource=epc" \
  --gzip \
  --collection=hce_docs \
  --drop \
  mongo_epc/hce_docs.bson.gz
```

> **Credenciales**: usuario `epc_user`, password `epc_strong_pass_2025`, authSource `epc`

---

## 🔷 Qdrant — Vector Brain (RAG)

### Propósito
Base de datos vectorial para **RAG (Retrieval-Augmented Generation)**. Almacena embeddings para búsqueda semántica de casos clínicos similares y feedback.

### Colecciones

| Colección | Vectores | Archivo | Descripción |
|-----------|----------|---------|-------------|
| `hce_chunks` | 0 | `qdrant_hce_chunks.snapshot` | Chunks de historias clínicas vectorizados para búsqueda semántica |
| `epc_feedback` | 0 | `qdrant_epc_feedback.snapshot` | Feedback vectorizado para few-shot learning |

> **Nota**: Las colecciones están vacías en este snapshot. Se poblan automáticamente cuando el sistema procesa HCEs y recibe feedback de médicos.

### Cómo Importar

```bash
# Restaurar colección hce_chunks
curl -X POST "http://localhost:6333/collections/hce_chunks/snapshots/upload" \
  -H "Content-Type:multipart/form-data" \
  -F "snapshot=@qdrant_hce_chunks.snapshot"

# Restaurar colección epc_feedback
curl -X POST "http://localhost:6333/collections/epc_feedback/snapshots/upload" \
  -H "Content-Type:multipart/form-data" \
  -F "snapshot=@qdrant_epc_feedback.snapshot"
```

> **Puerto por defecto**: `localhost:6333` (REST API)

---

## 🔴 Redis — No incluido

Redis es una capa **efímera** (cache, sesiones, rate limiting). No contiene datos persistentes críticos y se regenera automáticamente al iniciar el sistema. No se incluye dump.

---

## 🔄 Restauración Completa del Sistema (Paso a Paso)

Para restaurar **todo** el sistema desde estos dumps:

```bash
# 1. Asegurarse que los containers están corriendo
docker ps  # Verificar: postgres, redis, mongo, qdrant

# 2. Restaurar PostgreSQL
PGPASSWORD=ainstein_secure_2026 pg_restore -U ainstein -h localhost \
  -d ainstein --clean --if-exists dumps_20260225/postgres_ainstein.dump

# 3. Restaurar MongoDB
docker exec -i mongodb mongorestore \
  --uri="mongodb://epc_user:epc_strong_pass_2025@localhost:27017/epc?authSource=epc" \
  --gzip --drop /tmp/mongo_dump/epc
# O desde el host:
mongorestore --uri="mongodb://epc_user:epc_strong_pass_2025@localhost:27017/epc?authSource=epc" \
  --gzip --dir=dumps_20260225/mongo_epc/ --drop

# 4. Restaurar Qdrant
curl -X POST "http://localhost:6333/collections/hce_chunks/snapshots/upload" \
  -H "Content-Type:multipart/form-data" \
  -F "snapshot=@dumps_20260225/qdrant_hce_chunks.snapshot"

curl -X POST "http://localhost:6333/collections/epc_feedback/snapshots/upload" \
  -H "Content-Type:multipart/form-data" \
  -F "snapshot=@dumps_20260225/qdrant_epc_feedback.snapshot"

# 5. Verificar
curl http://localhost:8000/admin/health
```

---

*Generado automáticamente — AInstein FERRO D2 v3.0.0*
