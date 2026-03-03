# Dump Completo - 03/03/2026

## Contenido

| Archivo | Base de Datos | Tamaño | Documentos/Registros |
|---------|--------------|--------|---------------------|
| `postgres_epc_db_full.sql.gz` | PostgreSQL (ainstein) | 28 MB (comprimido) | Tablas: users, patients, admissions, roles, tenants |
| `mongo_epc_full/` | MongoDB (epc) | 29 MB | 17 colecciones, 2552+ documentos |
| `redis_dump.rdb` | Redis | < 1 KB | Cache y sesiones |
| `qdrant_hce_chunks.snapshot` | Qdrant | 58 KB | Colección hce_chunks |
| `qdrant_epc_feedback.snapshot` | Qdrant | 58 KB | Colección epc_feedback |
| `qdrant_epc_feedback_vectors.snapshot` | Qdrant | 45 KB | Colección epc_feedback_vectors |

## Colecciones MongoDB

| Colección | Documentos |
|-----------|-----------|
| hce_docs | 211 |
| epc_docs | 129 |
| epc_versions | 262 |
| epc_feedback | 518 |
| learning_rules | 628 |
| learning_problems | 315 |
| llm_usage | 419 |
| learning_events | 35 |
| epc_section_corrections | 24 |
| golden_rules | 8 |
| section_mapping_dictionary | 3 |

## Restauración

```bash
# PostgreSQL
PGPASSWORD=ainstein_secure_2026 psql -h localhost -U ainstein -d ainstein < postgres_epc_db_full.sql

# MongoDB
mongorestore --uri="mongodb://epc_user:epc_strong_pass_2025@localhost:27017/epc?authSource=epc" --db=epc --dir=mongo_epc_full --gzip --drop

# Redis
sudo systemctl stop redis
sudo cp redis_dump.rdb /var/lib/redis/dump.rdb
sudo chown redis:redis /var/lib/redis/dump.rdb
sudo systemctl start redis

# Qdrant
curl -X POST "http://localhost:6333/collections/hce_chunks/snapshots/upload" -F "snapshot=@qdrant_hce_chunks.snapshot"
curl -X POST "http://localhost:6333/collections/epc_feedback/snapshots/upload" -F "snapshot=@qdrant_epc_feedback.snapshot"
curl -X POST "http://localhost:6333/collections/epc_feedback_vectors/snapshots/upload" -F "snapshot=@qdrant_epc_feedback_vectors.snapshot"
```
