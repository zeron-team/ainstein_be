# Full Database Dump - 2026-02-28T20:09Z

## Contenido

### 1. PostgreSQL (`postgres_epc_db_full.sql`) - 85KB
Base de datos relacional completa (epc_db). Formato: pg_dump con COPY.

| Tabla | Registros |
|-------|-----------|
| tenants | 1 |
| roles | 3 |
| users | 12 |
| patients | 86 |
| patient_status | 82 |
| admissions | 108 |
| epc | 0 |
| epc_events | 277 |
| branding | 1 |
| abac_policies | - |
| abac_audit_log | - |
| tenant_api_keys | - |
| alembic_version | 1 |

### 2. MongoDB (`mongo_epc_full/`) - 29MB (gzip)
Base de datos documental completa (epc). Formato: mongodump --gzip.

| Colección | Documentos |
|-----------|------------|
| epc_docs | 128 |
| epc_feedback | 511 |
| epc_versions | 261 |
| hce_docs | 210 |
| learning_rules | 523 |
| learning_problems | 254 |
| llm_usage | 402 |
| learning_events | 33 |
| chat_history | 0 |
| epc_hce | 0 |
| epc_logs | 0 |
| hce | 0 |
| hce_docs_parsed | 0 |
| hce_parsed | 0 |

### 3. Qdrant (snapshots) - 188KB total
Colecciones vectoriales. Formato: snapshot nativo.

| Colección | Puntos | Archivo |
|-----------|--------|---------|
| epc_feedback | 0 | qdrant_epc_feedback.snapshot |
| epc_feedback_vectors | 0 | qdrant_epc_feedback_vectors.snapshot |
| hce_chunks | 0 | qdrant_hce_chunks.snapshot |

### 4. Redis (`redis_dump.rdb`) - 4KB
Cache/sesiones. Formato: RDB nativo. Keys: 0.

## Restauración

### PostgreSQL
```bash
cat postgres_epc_db_full.sql | docker exec -i ferro_postgres psql -U epc_user -d epc_db
```

### MongoDB
```bash
docker exec ferro_mongo mongorestore --uri="mongodb://epc_user:epc_strong_pass_2025@127.0.0.1:27017/epc?authSource=admin" --gzip --drop /tmp/mongodump
# First: docker cp mongo_epc_full ferro_mongo:/tmp/mongodump
```

### Qdrant
```bash
curl -X POST 'http://localhost:6333/collections/{COLLECTION}/snapshots/upload?priority=snapshot' \
     -H 'Content-Type: multipart/form-data' \
     -F 'snapshot=@qdrant_{COLLECTION}.snapshot'
```

### Redis
```bash
docker cp redis_dump.rdb ferro_redis:/data/dump.rdb
docker restart ferro_redis
```
